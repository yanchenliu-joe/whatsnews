"""Orchestrate daily narrative generation and persistence."""

from __future__ import annotations

from datetime import date

from app.database import get_connection
from app.narrative.generator import build_rule_based_script
from app.narrative.loader import load_ranked_articles, narrative_generated_at
from app.narrative.quality import run_quality_gate
from app.narrative.refine import refine_narrative_with_ai
from app.briefing_repository import get_latest_daily_report_date
from app.perspective.repository import get_ready_perspective
from app.narrative.repository import (
    get_ready_narrative,
    get_next_version,
    insert_narrative,
)
from app.narrative.voice_alignment import (
    build_missing_narrative_api,
    build_voice_alignment,
)


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _fail(stage: str, report_date: str, exc: Exception) -> dict:
    _log(
        "narrative_failed",
        report_date=report_date,
        stage=stage,
        error=str(exc)[:300],
    )
    return {
        "status": "error",
        "report_date": report_date,
        "stage": stage,
        "detail": str(exc)[:500],
    }


def generate_daily_narrative(
    report_date: date | None = None,
    *,
    regenerate: bool = False,
) -> dict:
    """
    Generate and persist a cross-topic daily morning narrative.

    Returns a stats dict suitable for scheduler/admin responses.
    """
    try:
        conn = get_connection()
    except Exception as e:
        return {"status": "error", "detail": str(e), "report_date": str(report_date or date.today())}

    cur = conn.cursor()
    try:
        target_date = report_date or get_latest_daily_report_date(cur) or date.today()
        date_str = str(target_date)
        if not regenerate:
            existing = get_ready_narrative(cur, target_date)
            if existing:
                _log("narrative_skipped", report_date=date_str, reason="ready_exists")
                return {
                    "status": "skipped",
                    "reason": "ready_exists",
                    "report_date": date_str,
                    "narrative_id": existing.get("id"),
                    "version": existing.get("version"),
                    **(existing.get("metadata") or {}),
                }

        perspective = get_ready_perspective(cur, target_date)
        articles, report_ids, topic_count, article_pool_count = load_ranked_articles(
            cur, target_date
        )
        if not articles:
            _log("narrative_skipped", report_date=date_str, reason="no_publishable_briefings")
            return {
                "status": "skipped",
                "reason": "no_publishable_briefings",
                "report_date": date_str,
                "diagnostics": {
                    "source_topic_count": 0,
                    "article_pool_count": 0,
                    "selected_article_count": 0,
                },
            }

        diagnostics_base = {
            "source_topic_count": topic_count,
            "article_pool_count": article_pool_count,
            "selected_article_count": len(articles),
        }

        _log(
            "narrative_started",
            report_date=date_str,
            articles=len(articles),
            pool=article_pool_count,
            topics=topic_count,
            perspective=bool(perspective and perspective.get("status") == "ready"),
            stage="load_source_articles",
        )

        try:
            script = build_rule_based_script(
                target_date,
                articles,
                report_ids,
                topic_count,
                perspective=perspective,
            )
            script.generated_at = narrative_generated_at()
        except Exception as e:
            conn.rollback()
            return _fail("generate_rule_based_script", date_str, e)

        try:
            refined, ai_status, model = refine_narrative_with_ai(script)
            script = refined
            script.ai_refine_status = ai_status
            if model:
                script.model = model
            if ai_status in ("ai_success", "ai_fallback"):
                base = script.generation_method or "rule_v1"
                script.generation_method = (
                    base if base.endswith("+ai") else f"{base}+ai"
                )
        except Exception as e:
            conn.rollback()
            return _fail("optional_ai_refine", date_str, e)

        try:
            quality = run_quality_gate(script)
            script.quality_gate = quality
        except Exception as e:
            conn.rollback()
            return _fail("quality_gate", date_str, e)

        if quality["passed"]:
            script.status = "ready"
            script.error_message = None
        else:
            script.status = "failed"
            script.error_message = "; ".join(quality.get("errors") or [])

        try:
            script.version = get_next_version(cur, target_date)
            narrative_id = insert_narrative(cur, script)
            conn.commit()
        except Exception as e:
            conn.rollback()
            return _fail("persist_narrative", date_str, e)

        perspective_meta = script.metadata or {}

        if script.status == "ready":
            _log(
                "narrative_success",
                report_date=date_str,
                version=script.version,
                word_count=script.word_count,
                ai_refine=ai_status,
                perspective_used=perspective_meta.get("perspective_used"),
            )
            return {
                "status": "success",
                "report_date": date_str,
                "narrative_id": narrative_id,
                "version": script.version,
                "word_count": script.word_count,
                "section_count": len(script.sections),
                "estimated_duration_seconds": script.estimated_duration_seconds,
                "ai_refine_status": ai_status,
                "quality_gate": quality,
                "diagnostics": {
                    **diagnostics_base,
                    "generated_word_count": script.word_count,
                    "quality_warnings": quality.get("warnings") or [],
                    "quality_errors": quality.get("errors") or [],
                },
                **perspective_meta,
            }

        _log(
            "narrative_failed",
            report_date=date_str,
            error=script.error_message,
            word_count=script.word_count,
            topics=topic_count,
            articles=len(articles),
        )
        return {
            "status": "failed",
            "report_date": date_str,
            "narrative_id": narrative_id,
            "version": script.version,
            "error_message": script.error_message,
            "quality_gate": quality,
            "diagnostics": {
                **diagnostics_base,
                "generated_word_count": script.word_count,
                "section_count": len(script.sections),
                "quality_warnings": quality.get("warnings") or [],
                "quality_errors": quality.get("errors") or [],
            },
            **perspective_meta,
        }

    except Exception as e:
        conn.rollback()
        return _fail("unknown", date_str, e)
    finally:
        cur.close()
        conn.close()


def load_narrative_for_api(
    report_date: date | None = None,
    *,
    scope: str = "daily",
) -> dict | None:
    """
    Load narrative for public API.

    When report_date is omitted, anchors on the latest publishable daily report date
    instead of falling back to an older ready narrative/audio.
    """
    try:
        conn = get_connection()
    except Exception:
        return None

    cur = conn.cursor()
    try:
        if report_date is None:
            latest_report = get_latest_daily_report_date(cur)
            if not latest_report:
                return None

            alignment = build_voice_alignment(cur, anchor_date=latest_report)
            narrative = get_ready_narrative(cur, latest_report, scope=scope)
            if narrative:
                narrative["voice_alignment"] = alignment
                return narrative

            return build_missing_narrative_api(cur, latest_report)

        narrative = get_ready_narrative(cur, report_date, scope=scope)
        if narrative:
            narrative["voice_alignment"] = build_voice_alignment(
                cur, anchor_date=report_date
            )
        return narrative
    finally:
        cur.close()
        conn.close()
