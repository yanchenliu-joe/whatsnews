"""
Ingest -> assemble -> generate -> notify pipeline orchestration.

The ~15 nested lazy imports inside run_scheduled_pipeline() (editorial/
perspective/watch_next/narrative/ingestion.og_image) are DELIBERATELY left
lazy/local, exactly where they were in the original main.py — each sits
inside a per-stage try/except for fault isolation. Hoisting them to
top-of-file imports would change the failure mode: a broken import in any
one of those packages would then crash the whole app at startup (since
main.py's lifespan()/scheduler.py both import this module to start the
scheduler loop) instead of just degrading that one pipeline stage.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.analytics.events import _record_event
from app.assembly import assemble_all_active_topics, assemble_report_for_topic
from app.database import get_connection
from app.ingestion import ingest_all_active_sources, ingest_sources_for_topic
from app.log_utils import _log
from app.notifications.device_scheduler import (
    _FALLBACK_PUSH_COPY,
    _build_push_copy,
    _immediate_group_devices,
    _mark_devices_pushed,
)
from app.notifications.push import _send_push_to_tokens
from app.wim.config import get_wim_topic_concurrency
from app.wim.metrics import (
    empty_generation_stats,
    merge_generation_totals,
    normalize_generation_stats,
)
from app.wim.service import fill_missing_why_it_matters as _fill_missing_why_it_matters


def run_generation_for_topic(
    cur,
    conn,
    topic_name: str,
    report_id: int,
    report_date,
    trigger_type: str,
) -> dict:
    """
    Instrumented generation wrapper for a single topic's report.

    - Creates a generation_runs row with status='running' at the start.
    - Calls _fill_missing_why_it_matters() to generate and persist why_it_matters.
    - Updates the run row to 'success' or 'failed' with full metrics.
    - If the generation_runs table does not exist yet, logs a warning and continues
      without tracking (schema migration not yet applied).

    Returns a summary dict with run_id, status, and article counts.
    """
    started_at = datetime.now(tz=ZoneInfo("UTC"))
    run_id = None

    # Open the run record. If the table doesn't exist yet, skip tracking gracefully.
    try:
        cur.execute(
            """
            INSERT INTO generation_runs
                (topic, trigger_type, status, report_date, started_at)
            VALUES (%s, %s, 'running', %s, %s)
            RETURNING id
            """,
            (topic_name, trigger_type, report_date, started_at),
        )
        run_id = cur.fetchone()["id"]
        conn.commit()
    except Exception:
        conn.rollback()
        _log("generation_run_tracking_unavailable", topic=topic_name,
             note="Run schema.sql migration to enable generation_runs tracking")

    _log("generation_started", topic=topic_name, trigger=trigger_type, run_id=run_id)

    try:
        # Fetch articles for this report.
        cur.execute(
            """
            SELECT id, title, summary, source, url, why_it_matters, editorial_metadata
            FROM articles
            WHERE report_id = %s
            ORDER BY id ASC
            """,
            (report_id,),
        )
        articles = [dict(r) for r in cur.fetchall()]
        _log("generation_articles_built", topic=topic_name, run_id=run_id, count=len(articles))

        # Generate and persist why_it_matters for any missing articles.
        counts = _fill_missing_why_it_matters(cur, articles, topic_name)
        conn.commit()
        _log("generation_persisted", topic=topic_name, run_id=run_id,
             generated=counts["articles_generated"])

        if counts["ai_refine_attempted"] > 0:
            _log("generation_ai_refine_done", topic=topic_name, run_id=run_id,
                 attempted=counts["ai_refine_attempted"],
                 success=counts["ai_refine_success"],
                 fallback=counts["ai_refine_fallback"])

        if counts.get("wim_requests", 0) > 0:
            _log(
                "generation_wim_batch_done",
                topic=topic_name,
                run_id=run_id,
                wim_requests=counts.get("wim_requests"),
                wim_articles_generated=counts.get("wim_articles_generated"),
                average_articles_per_request=counts.get("average_articles_per_request"),
            )

        finished_at = datetime.now(tz=ZoneInfo("UTC"))
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        # Update run record to success.
        if run_id is not None:
            try:
                cur.execute(
                    """
                    UPDATE generation_runs SET
                        status                   = 'success',
                        finished_at              = %s,
                        duration_ms              = %s,
                        articles_count           = %s,
                        ai_refine_attempted      = %s,
                        ai_refine_success_count  = %s,
                        ai_refine_fallback_count = %s
                    WHERE id = %s
                    """,
                    (
                        finished_at, duration_ms,
                        counts["articles_checked"],
                        counts["ai_refine_attempted"],
                        counts["ai_refine_success"],
                        counts["ai_refine_fallback"],
                        run_id,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()

        _log("generation_completed", topic=topic_name, run_id=run_id,
             articles_checked=counts["articles_checked"],
             articles_generated=counts["articles_generated"],
             duration_ms=duration_ms)

        return {"run_id": run_id, "status": "success", **counts}

    except Exception as e:
        finished_at = datetime.now(tz=ZoneInfo("UTC"))
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        error_msg = str(e)[:1000]

        _log("generation_failed", topic=topic_name, run_id=run_id,
             duration_ms=duration_ms, error=error_msg)

        if run_id is not None:
            try:
                cur.execute(
                    """
                    UPDATE generation_runs SET
                        status        = 'failed',
                        finished_at   = %s,
                        duration_ms   = %s,
                        error_message = %s
                    WHERE id = %s
                    """,
                    (finished_at, duration_ms, error_msg, run_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()

        raise


def _run_generation_for_topic_row(topic_row: dict) -> dict | None:
    """Generate WIM for one topic's daily report (isolated DB connection)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, report_date
                FROM daily_reports
                WHERE topic_id = %s AND report_date = CURRENT_DATE
                """,
                (topic_row["id"],),
            )
            report = cur.fetchone()
            if not report:
                _log(
                    "scheduler_topic_skipped",
                    topic=topic_row["name"],
                    reason="no daily_report for today",
                )
                return None
            return run_generation_for_topic(
                cur=cur,
                conn=conn,
                topic_name=topic_row["name"],
                report_id=report["id"],
                report_date=report["report_date"],
                trigger_type="scheduler",
            )
        finally:
            cur.close()
    except Exception as e:
        _log("scheduler_topic_error", topic=topic_row["name"], error=str(e))
        raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _merge_generation_result(totals: dict, result: dict) -> None:
    merge_generation_totals(totals, result)


def run_scheduled_preparation() -> dict:
    """
    Synchronous work unit for the scheduler.
    Runs in a thread pool so it does not block the async event loop.

    Generates why_it_matters for today's daily report on every active topic.
    Uses a fresh DB connection per topic so one failure cannot poison others.
    """
    totals = empty_generation_stats()

    try:
        list_conn = get_connection()
    except ValueError:
        _log("scheduler_skipped", reason="DATABASE_URL not set")
        totals["status"] = "skipped"
        return normalize_generation_stats(totals)

    list_cur = list_conn.cursor()
    list_cur.execute(
        "SELECT id, name FROM topics WHERE is_active = TRUE ORDER BY sort_order ASC, name ASC"
    )
    topics = [dict(r) for r in list_cur.fetchall()]
    list_cur.close()
    list_conn.close()

    if not topics:
        _log("scheduler_skipped", reason="no active topics in database")
        totals["status"] = "skipped"
        return normalize_generation_stats(totals)

    workers = min(len(topics), get_wim_topic_concurrency())
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_run_generation_for_topic_row, topic_row): topic_row
            for topic_row in topics
        }
        for future in as_completed(futures):
            topic_row = futures[future]
            try:
                result = future.result()
                if result is not None:
                    _merge_generation_result(totals, result)
            except Exception:
                totals["status"] = "partial"
                _log("scheduler_topic_error", topic=topic_row["name"], error="generation_failed")

    if totals["wim_requests"]:
        totals["average_articles_per_request"] = round(
            totals["batch_articles"] / totals["wim_requests"], 2
        )

    finalized = normalize_generation_stats(totals)
    _log(
        "generation_batch_summary",
        topics=finalized["topics_processed"],
        wim_requests=finalized["wim_requests"],
        wim_articles_generated=finalized["wim_articles_generated"],
        average_articles_per_request=finalized["average_articles_per_request"],
        wim_cache_hits=finalized["wim_cache_hits"],
        wim_fallback_count=finalized["wim_fallback_count"],
    )
    return finalized


def run_scheduled_pipeline(regenerate: bool = False) -> dict:
    """
    Full scheduled pipeline: ingest → assemble → generate.

    Each step manages its own database connection and error handling.
    A failure in one step is logged but does not prevent subsequent steps
    from running — previously ingested or assembled data can still be processed.

    `regenerate` (Phase 34, added 2026-07-06): when True, forces the
    perspective/watch-next/narrative stages to produce a fresh version even
    if today's is already "ready" — used by the daily-mode scheduler, which
    now wakes for multiple configured slots per day rather than once, so each
    slot should refresh content rather than skip because today's already
    exists. Defaults to False so admin_run_pipeline()'s manual trigger and
    interval-mode dev runs don't force paid AI/TTS regeneration on every call.
    Assembly/editorial/WIM are unaffected by this flag — they already
    re-evaluate and replace today's selection on every call regardless.

    Returns a stats dict summarising each step.  The scheduler caller
    ignores the return value; the admin endpoint surfaces it as JSON.
    """
    pipeline_started = time.perf_counter()
    timing: dict[str, float] = {}
    _log("pipeline_started")
    stats: dict = {
        "status": "completed",
        "ingest": None,
        "assembly": None,
        "editorial_engine": None,
        "generation": None,
        "editorial_perspective": None,
        "watch_next": None,
        "narrative": None,
        "narrative_audio": None,
    }

    stage_start = time.perf_counter()
    try:
        ingest_result = ingest_all_active_sources()
        stats["ingest"] = ingest_result
        _log("pipeline_ingest_done",
             topics=ingest_result.get("topics_processed", 0),
             inserted=ingest_result.get("articles_inserted", 0),
             skipped=ingest_result.get("articles_skipped", 0),
             errors=ingest_result.get("errors_count", 0))
    except Exception as e:
        stats["ingest"] = {"error": str(e)[:500]}
        _log("pipeline_ingest_failed", error=str(e)[:500])
    timing["ingest"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    try:
        assembly_result = assemble_all_active_topics()
        stats["assembly"] = assembly_result
        _log("pipeline_assembly_done",
             topics=assembly_result.get("topics_processed", 0),
             assigned=assembly_result.get("total_assigned", 0),
             errors=assembly_result.get("errors_count", 0))
    except Exception as e:
        stats["assembly"] = {"error": str(e)[:500]}
        _log("pipeline_assembly_failed", error=str(e)[:500])
    timing["assembly"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    try:
        from app.ingestion.og_image import fill_missing_og_images

        og_result = fill_missing_og_images()
        stats["og_images"] = og_result
        _log(
            "pipeline_og_images_done",
            checked=og_result.get("articles_checked"),
            fetched=og_result.get("fetched"),
            updated=og_result.get("updated"),
        )
    except Exception as e:
        stats["og_images"] = {"error": str(e)[:300]}
        _log("pipeline_og_images_failed", error=str(e)[:300])
    timing["og_images"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    try:
        from app.editorial.metrics import normalize_editorial_stats
        from app.editorial.service import run_editorial_engine

        editorial_result = run_editorial_engine()
        stats["editorial_engine"] = editorial_result
        _log(
            "pipeline_editorial_engine_done",
            articles=editorial_result.get("articles_processed"),
            average_importance=editorial_result.get("average_importance"),
            persisted=editorial_result.get("metadata_persisted"),
        )
    except Exception as e:
        from app.editorial.metrics import normalize_editorial_stats

        stats["editorial_engine"] = normalize_editorial_stats(
            {"status": "failed", "error": str(e)[:500]}
        )
        _log("pipeline_editorial_engine_failed", error=str(e)[:500])
    timing["editorial"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    try:
        generation_result = run_scheduled_preparation()
        stats["generation"] = generation_result
        _log(
            "pipeline_generation_done",
            wim_requests=generation_result.get("wim_requests"),
            wim_articles_generated=generation_result.get("wim_articles_generated"),
            average_articles_per_request=generation_result.get(
                "average_articles_per_request"
            ),
            wim_cache_hits=generation_result.get("wim_cache_hits"),
            wim_fallback_count=generation_result.get("wim_fallback_count"),
        )
    except Exception as e:
        stats["generation"] = normalize_generation_stats(
            {"status": "failed", "error": str(e)[:500]}
        )
        _log("pipeline_generation_failed", error=str(e)[:500])
    timing["why_it_matters"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    try:
        from app.perspective.service import generate_daily_perspective

        perspective_result = generate_daily_perspective(regenerate=regenerate)
        stats["editorial_perspective"] = perspective_result
        _log(
            "pipeline_perspective_done",
            status=perspective_result.get("perspective_status"),
            confidence=perspective_result.get("perspective_confidence"),
            supporting=perspective_result.get("perspective_supporting_article_count"),
        )
    except Exception as e:
        from app.perspective.metrics import normalize_perspective_stats

        stats["editorial_perspective"] = normalize_perspective_stats(
            {"status": "error", "perspective_status": "failed", "error": str(e)[:500]}
        )
        _log("pipeline_perspective_failed", error=str(e)[:500])
    timing["perspective"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    try:
        from app.watch_next.service import generate_daily_watch_next

        watch_next_result = generate_daily_watch_next(regenerate=regenerate)
        stats["watch_next"] = watch_next_result
        _log(
            "pipeline_watch_next_done",
            status=watch_next_result.get("watch_next_status"),
            items=watch_next_result.get("watch_next_item_count"),
        )
    except Exception as e:
        from app.watch_next.metrics import normalize_watch_next_stats

        stats["watch_next"] = normalize_watch_next_stats(
            {"status": "error", "watch_next_status": "failed", "error": str(e)[:500]}
        )
        _log("pipeline_watch_next_failed", error=str(e)[:500])
    timing["watch_next"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    narrative_report_date: date | None = None
    try:
        from app.narrative.service import generate_daily_narrative

        narrative_result = generate_daily_narrative(regenerate=regenerate)
        stats["narrative"] = narrative_result
        report_date_str = narrative_result.get("report_date")
        if report_date_str:
            try:
                narrative_report_date = date.fromisoformat(str(report_date_str))
            except ValueError:
                narrative_report_date = None
        _log(
            "pipeline_narrative_done",
            status=narrative_result.get("status"),
            report_date=narrative_result.get("report_date"),
        )
    except Exception as e:
        stats["narrative"] = {"error": str(e)[:500]}
        _log("pipeline_narrative_failed", error=str(e)[:500])
    timing["narrative"] = round(time.perf_counter() - stage_start, 2)

    stage_start = time.perf_counter()
    from app.narrative.audio_config import audio_enabled_in_scheduler

    if audio_enabled_in_scheduler():
        try:
            from app.narrative.audio_service import generate_all_narrative_audio_variants

            audio_result = generate_all_narrative_audio_variants(
                narrative_report_date,
                narrative_result=stats.get("narrative"),
            )
            stats["narrative_audio"] = audio_result
            _log(
                "pipeline_narrative_audio_done",
                status=audio_result.get("status"),
                report_date=audio_result.get("report_date"),
                female=audio_result.get("profiles", {}).get("female", {}).get("status"),
                male=audio_result.get("profiles", {}).get("male", {}).get("status"),
            )
        except Exception as e:
            err = str(e)[:500]
            stats["narrative_audio"] = {
                "status": "failed",
                "reason": err,
                "profiles": {
                    "female": {"status": "failed", "error_message": err},
                    "male": {"status": "failed", "error_message": err},
                },
            }
            _log("pipeline_narrative_audio_failed", error=err)
    else:
        stats["narrative_audio"] = {
            "status": "skipped",
            "reason": "audio_generation_disabled",
            "profiles": {
                "female": {"status": "skipped"},
                "male": {"status": "skipped"},
            },
        }
        _log("pipeline_narrative_audio_skipped", reason="audio_generation_disabled")
    timing["audio"] = round(time.perf_counter() - stage_start, 2)

    if any(
        isinstance(stats[k], dict) and "error" in stats[k]
        for k in ("ingest", "assembly", "generation")
        if stats[k]
    ):
        stats["status"] = "partial"

    timing["total"] = round(time.perf_counter() - pipeline_started, 2)
    stats["timing_seconds"] = timing

    try:
        from app.narrative.voice_alignment import build_voice_alignment, get_pipeline_dates_summary

        conn = get_connection()
        cur = conn.cursor()
        try:
            stats["dates"] = get_pipeline_dates_summary(cur)
            stats["voice"] = build_voice_alignment(cur)
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        stats["voice"] = {"voice_status": "failed", "message": str(e)[:200]}

    _log(
        "pipeline_completed",
        total_seconds=timing["total"],
        ingest=timing["ingest"],
        assembly=timing["assembly"],
        editorial=timing.get("editorial"),
        why_it_matters=timing["why_it_matters"],
        perspective=timing.get("perspective"),
        watch_next=timing.get("watch_next"),
        narrative=timing["narrative"],
        audio=timing["audio"],
    )
    if stats.get("generation") is None:
        stats["generation"] = empty_generation_stats()
    else:
        stats["generation"] = normalize_generation_stats(stats["generation"])
    if stats.get("editorial_engine") is None:
        from app.editorial.metrics import empty_editorial_stats

        stats["editorial_engine"] = empty_editorial_stats()
    else:
        from app.editorial.metrics import normalize_editorial_stats

        stats["editorial_engine"] = normalize_editorial_stats(stats["editorial_engine"])
    if stats.get("editorial_perspective") is None:
        from app.perspective.metrics import empty_perspective_stats

        stats["editorial_perspective"] = empty_perspective_stats()
    else:
        from app.perspective.metrics import normalize_perspective_stats

        stats["editorial_perspective"] = normalize_perspective_stats(
            stats["editorial_perspective"]
        )
    if stats.get("watch_next") is None:
        from app.watch_next.metrics import empty_watch_next_stats

        stats["watch_next"] = empty_watch_next_stats()
    else:
        from app.watch_next.metrics import normalize_watch_next_stats

        stats["watch_next"] = normalize_watch_next_stats(stats["watch_next"])
    return stats


def run_generation_pipeline_for_topic(
    conn,
    cur,
    topic_id: int,
    topic_name: str,
    trigger_type: str,
) -> dict:
    """
    Full per-topic pipeline: ingest RSS → assemble today's report → generate.

    Ingest failures are logged but do not block assembly or generation so
    previously ingested candidates can still be used.  Assembly must succeed
    before generation runs.

    Returns run_generation_for_topic() fields plus:
      articles_assigned          — articles linked to today's report by assembly
      why_it_matters_generated   — same meaning as articles_generated (legacy name)
    """
    _log("pipeline_topic_started", topic=topic_name, trigger=trigger_type)

    try:
        ingest_stats = ingest_sources_for_topic(conn, topic_id, topic_name)
        _log(
            "pipeline_topic_ingest_done",
            topic=topic_name,
            inserted=ingest_stats.get("articles_inserted", 0),
            skipped=ingest_stats.get("articles_skipped", 0),
            errors=ingest_stats.get("errors", 0),
        )
    except Exception as e:
        _log("pipeline_topic_ingest_failed", topic=topic_name, error=str(e)[:500])

    assembly_stats = assemble_report_for_topic(conn, topic_id, topic_name)
    _log(
        "pipeline_topic_assembly_done",
        topic=topic_name,
        report_id=assembly_stats["report_id"],
        assigned=assembly_stats["articles_assigned"],
    )

    result = run_generation_for_topic(
        cur=cur,
        conn=conn,
        topic_name=topic_name,
        report_id=assembly_stats["report_id"],
        report_date=date.fromisoformat(assembly_stats["report_date"]),
        trigger_type=trigger_type,
    )
    return {
        **result,
        "articles_assigned": assembly_stats["articles_assigned"],
        "why_it_matters_generated": result["articles_generated"],
    }


def _notify_after_pipeline(pipeline_stats: dict) -> None:
    """
    Send a push notification after a scheduled pipeline run completes.
    Only fires when the pipeline finished (status 'completed' or 'partial').
    Uses dynamic copy from the top story when available, otherwise falls back
    to safe fixed copy.  Never raises — failures are logged and swallowed.

    Phase 34: only devices with no notification_time preference get pushed
    here — the "immediate" group, same behavior everyone had before this
    phase. Devices that set a preferred delivery time are instead handled by
    _run_device_notification_tick(), which delivers once their local time
    arrives (today's content is already ready by definition, since this
    function only runs after the pipeline finishes).

    With multiple daily pipeline slots (added same phase, 2026-07-06): the
    immediate group is deliberately pushed only once per day, from whichever
    slot finishes first — _immediate_group_devices()'s dedup guard means a
    2nd/3rd slot's call here just refreshes content for everyone without
    re-notifying this group.
    """
    status = pipeline_stats.get("status")
    if status not in ("completed", "partial"):
        _log("scheduled_push_skipped", reason="pipeline_status_" + str(status))
        return

    title, body, data = _build_push_copy()
    copy_type = "dynamic" if (title, body, data) != _FALLBACK_PUSH_COPY else "fallback"
    _log("scheduled_push_starting", copy=copy_type, body_preview=body[:80])

    server_tz_name = os.getenv("SCHEDULER_TIMEZONE", "UTC")
    try:
        server_tz = ZoneInfo(server_tz_name)
    except Exception:
        server_tz = ZoneInfo("UTC")
    server_today = datetime.now(tz=ZoneInfo("UTC")).astimezone(server_tz).date()

    devices = _immediate_group_devices(server_today)
    tokens = [d["push_token"] for d in devices]
    result = _send_push_to_tokens(tokens, title, body, data)
    _log("scheduled_push_done", push_status=result.get("status"),
         sent=result.get("sent"), errors=result.get("errors"))

    if result.get("status") == "ok" and result.get("sent", 0) > 0:
        _mark_devices_pushed([d["id"] for d in devices], server_today)
        _record_event("push_sent", metadata_text=f"sent={result['sent']} copy={copy_type}")
