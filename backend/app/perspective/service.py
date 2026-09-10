"""Orchestrate daily editorial perspective generation."""

from __future__ import annotations

import time
from datetime import date

from app.briefing_repository import get_latest_daily_report_date
from app.database import get_connection
from app.perspective.generator import build_rule_based_perspective
from app.perspective.loader import load_perspective_articles
from app.perspective.metrics import normalize_perspective_stats
from app.perspective.quality import run_perspective_quality_gate
from app.perspective.refine import refine_perspective_with_ai
from app.perspective.repository import (
    get_ready_perspective,
    get_next_version,
    insert_perspective,
)


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _stats_from_result(result: dict, elapsed: float) -> dict:
    perspective = result.get("perspective") or {}
    return normalize_perspective_stats(
        {
            "status": result.get("status", "completed"),
            "perspective_status": perspective.get("status") or result.get("perspective_status"),
            "perspective_confidence": perspective.get("confidence")
            or result.get("perspective_confidence"),
            "perspective_theme_count": len(perspective.get("themes") or [])
            or result.get("perspective_theme_count", 0),
            "perspective_supporting_article_count": len(
                perspective.get("supporting_evidence") or []
            )
            or result.get("perspective_supporting_article_count", 0),
            "perspective_generation_seconds": elapsed,
            "perspective_id": result.get("perspective_id"),
            "version": result.get("version"),
            "quality_gate": result.get("quality_gate"),
            "reason": result.get("reason"),
            "error": result.get("error"),
        }
    )


def generate_daily_perspective(
    report_date: date | None = None,
    *,
    regenerate: bool = False,
) -> dict:
    """
    Generate and persist a daily editorial perspective.

    Does not raise — returns stats dict for pipeline/admin use.
    """
    started = time.perf_counter()
    try:
        conn = get_connection()
    except ValueError as exc:
        elapsed = time.perf_counter() - started
        return _stats_from_result(
            {
                "status": "error",
                "perspective_status": "failed",
                "error": str(exc)[:500],
            },
            elapsed,
        )

    cur = conn.cursor()
    try:
        target_date = report_date or get_latest_daily_report_date(cur) or date.today()
        date_str = str(target_date)

        if not regenerate:
            existing = get_ready_perspective(cur, target_date)
            if existing:
                _log("perspective_skipped", report_date=date_str, reason="ready_exists")
                elapsed = time.perf_counter() - started
                return _stats_from_result(
                    {
                        "status": "skipped",
                        "reason": "ready_exists",
                        "perspective_status": "ready",
                        "perspective_confidence": existing.get("confidence"),
                        "perspective_theme_count": len(existing.get("themes") or []),
                        "perspective_supporting_article_count": len(
                            existing.get("supporting_evidence") or []
                        ),
                        "perspective_id": existing.get("id"),
                        "version": existing.get("version"),
                    },
                    elapsed,
                )

        articles, topic_count = load_perspective_articles(cur, target_date)
        if not articles:
            _log("perspective_skipped", report_date=date_str, reason="no_publishable_articles")
            elapsed = time.perf_counter() - started
            return _stats_from_result(
                {
                    "status": "skipped",
                    "reason": "no_publishable_articles",
                    "perspective_status": "missing",
                },
                elapsed,
            )

        _log(
            "perspective_started",
            report_date=date_str,
            articles=len(articles),
            topics=topic_count,
        )

        perspective = build_rule_based_perspective(target_date, articles)
        source_titles = [a.title for a in articles[:5]]
        perspective, ai_status, _model = refine_perspective_with_ai(
            perspective, source_titles=source_titles
        )
        if ai_status == "ai_success":
            _log("perspective_ai_refine_success", report_date=date_str)

        quality = run_perspective_quality_gate(perspective)
        perspective.quality_gate = quality

        if quality["passed"]:
            perspective.status = "ready"
            perspective.error_message = None
        else:
            perspective.status = "failed"
            perspective.error_message = "; ".join(quality.get("errors") or [])

        perspective.version = get_next_version(cur, target_date)
        perspective_id = insert_perspective(cur, perspective)
        conn.commit()

        elapsed = time.perf_counter() - started
        result = {
            "status": "success" if perspective.status == "ready" else "failed",
            "report_date": date_str,
            "perspective_id": perspective_id,
            "version": perspective.version,
            "perspective_status": perspective.status,
            "perspective_confidence": perspective.confidence,
            "perspective_theme_count": len(perspective.themes),
            "perspective_supporting_article_count": len(perspective.supporting_evidence),
            "quality_gate": quality,
            "perspective": perspective.to_dict(),
            "ai_refine_status": ai_status,
        }

        if perspective.status == "ready":
            _log(
                "perspective_success",
                report_date=date_str,
                version=perspective.version,
                confidence=perspective.confidence,
                themes=len(perspective.themes),
            )
        else:
            _log(
                "perspective_failed",
                report_date=date_str,
                error=perspective.error_message,
            )

        return _stats_from_result(result, elapsed)

    except Exception as exc:
        conn.rollback()
        elapsed = time.perf_counter() - started
        _log("perspective_error", error=str(exc)[:300])
        return _stats_from_result(
            {
                "status": "error",
                "perspective_status": "failed",
                "error": str(exc)[:500],
            },
            elapsed,
        )
    finally:
        cur.close()
        conn.close()


def load_perspective_for_api(report_date: date | None = None) -> dict | None:
    """
    Load perspective for public API.

    Returns ready perspective dict, or missing-state dict when anchored date
    has no ready perspective yet.
    """
    try:
        conn = get_connection()
    except ValueError:
        return None

    cur = conn.cursor()
    try:
        if report_date is None:
            anchor = get_latest_daily_report_date(cur)
            if not anchor:
                return None
            report_date = anchor

        ready = get_ready_perspective(cur, report_date)
        if ready:
            return ready

        return {
            "report_date": str(report_date),
            "status": "missing",
            "headline": None,
            "perspective": None,
            "supporting_evidence": [],
            "watch_next": [],
            "confidence": None,
            "themes": [],
        }
    finally:
        cur.close()
        conn.close()
