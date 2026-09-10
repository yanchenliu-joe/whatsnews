"""Admin routes that trigger a pipeline side effect (ingest/assemble/generate/push)."""

from __future__ import annotations

import time
from datetime import date
from typing import Optional

import psycopg2
from fastapi import FastAPI, Header, HTTPException

from app.assembly import assemble_all_active_topics
from app.database import get_connection
from app.ingestion import ingest_all_active_sources
from app.log_utils import _log
from app.notifications.push import _send_push_to_all_devices
from app.pipeline.orchestrator import (
    _notify_after_pipeline,
    run_generation_pipeline_for_topic,
    run_scheduled_pipeline,
    run_scheduled_preparation,
)
from app.retention.service import run_archive_cleanup
from app.wim.metrics import normalize_generation_stats


def register_admin_pipeline_routes(app: FastAPI, require_admin_key) -> None:
    """Attach /admin/* pipeline-trigger endpoints. require_admin_key is app.admin.deps.require_admin_key."""

    @app.post("/admin/generate-report")
    def admin_generate_report(
        topic: str,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Prepare a daily report for the given topic.

        Runs the full per-topic pipeline: ingest latest RSS, assemble today's
        report from real candidate articles, generate why_it_matters for any
        articles that are missing it, and record the run in generation_runs.

        Response includes articles_assigned (report-linked count) and
        why_it_matters_generated (new insights written).  articles_generated
        is kept for backward compatibility and matches why_it_matters_generated.

        Protected by ADMIN_API_KEY when that environment variable is set.
        Pass the key via the x-admin-key request header.
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            cur.execute("SELECT id, name, is_active FROM topics WHERE name = %s", (topic,))
            topic_row = cur.fetchone()
            if not topic_row:
                cur.close()
                conn.close()
                raise HTTPException(status_code=404, detail=f"Topic '{topic}' not found.")
            if not topic_row["is_active"]:
                cur.close()
                conn.close()
                raise HTTPException(status_code=422, detail=f"Topic '{topic}' is inactive.")

            result = run_generation_pipeline_for_topic(
                conn=conn,
                cur=cur,
                topic_id=topic_row["id"],
                topic_name=topic_row["name"],
                trigger_type="admin",
            )

            cur.execute(
                """
                SELECT report_date
                FROM daily_reports
                WHERE topic_id = %s AND report_date = CURRENT_DATE
                """,
                (topic_row["id"],),
            )
            report = cur.fetchone()
            report_date = str(report["report_date"]) if report else str(date.today())

            cur.close()
            conn.close()

            return {
                "topic": topic_row["name"],
                "report_date": report_date,
                "run_id": result["run_id"],
                "status": result["status"],
                "articles_checked": result["articles_checked"],
                "articles_generated": result["articles_generated"],
                "articles_assigned": result["articles_assigned"],
                "why_it_matters_generated": result["why_it_matters_generated"],
                "ai_refine_attempted": result["ai_refine_attempted"],
                "ai_refine_success": result["ai_refine_success"],
                "ai_refine_fallback": result["ai_refine_fallback"],
            }

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.post("/admin/ingest")
    def admin_ingest(x_admin_key: Optional[str] = Header(default=None)):
        """
        Run RSS ingestion across all active topics and sources.
        Fetches feeds, normalises entries, and inserts new articles with
        content_hash deduplication.  Does not create reports or trigger generation.

        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)
        _log("admin_ingest_triggered")

        try:
            result = ingest_all_active_sources()
        except Exception as e:
            _log("ingestion_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Ingestion error. Please try again.")

        return result

    @app.post("/admin/assemble")
    def admin_assemble(x_admin_key: Optional[str] = Header(default=None)):
        """
        Run report assembly across all active topics.
        Selects top candidate articles and assigns them to today's daily report,
        then generates why_it_matters for any newly assigned articles.

        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)
        _log("admin_assemble_triggered")

        try:
            result = assemble_all_active_topics()
        except Exception as e:
            _log("assembly_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Assembly error. Please try again.")

        try:
            _log("admin_assemble_generation_starting")
            generation_result = run_scheduled_preparation()
            _log("admin_assemble_generation_done")
            result["generation"] = generation_result
        except Exception as e:
            _log("admin_assemble_generation_failed", error=str(e)[:500])
            result["generation"] = normalize_generation_stats(
                {"status": "failed", "error": str(e)[:500]}
            )

        return result

    @app.post("/admin/backfill-body-text")
    def admin_backfill_body_text(
        x_admin_key: Optional[str] = Header(default=None),
        days: int = 7,
        limit: int = 100,
    ):
        """
        Retroactively scrape body_text for assembled articles that are missing it.
        Looks at articles linked to reports from the past `days` days.
        Processes up to `limit` articles per call.
        """
        require_admin_key(x_admin_key)
        from app.ingestion.scrape import scrape_body_texts_concurrent
        from app.ingestion.normalize import improve_summary_from_body

        _log("admin_backfill_body_text_started", days=days, limit=limit)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.id, a.url, a.summary
                FROM articles a
                JOIN daily_reports dr ON a.report_id = dr.id
                WHERE (a.body_text IS NULL OR a.body_text = '')
                  AND a.url IS NOT NULL AND a.url != ''
                  AND dr.report_date >= CURRENT_DATE - %s
                ORDER BY dr.report_date DESC, a.id
                LIMIT %s
                """,
                (days, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]

            if not rows:
                cur.close()
                conn.close()
                return {"status": "ok", "attempted": 0, "filled": 0, "message": "No articles need backfill."}

            scraped = scrape_body_texts_concurrent(rows, max_workers=6)

            filled = 0
            for row in rows:
                text = scraped.get(row["url"])
                if text:
                    # Scraped body_text is never shown as full text in the app
                    # (dropped from Read mode 2026-07-11) — used here purely as
                    # raw material to lengthen a too-short summary, the only
                    # content mobile actually displays.
                    new_summary = improve_summary_from_body(row["summary"] or "", text)
                    cur.execute(
                        "UPDATE articles SET body_text = %s, summary = %s WHERE id = %s",
                        (text, new_summary, row["id"]),
                    )
                    filled += 1

            conn.commit()
            cur.close()
            conn.close()

            _log("admin_backfill_body_text_done", attempted=len(rows), filled=filled)
            return {
                "status": "ok",
                "attempted": len(rows),
                "filled": filled,
                "skipped": len(rows) - filled,
            }
        except Exception as e:
            _log("backfill_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Backfill error. Please try again.")

    @app.post("/admin/archive-cleanup")
    def admin_archive_cleanup(
        x_admin_key: Optional[str] = Header(default=None),
        retention_days: Optional[int] = None,
        product_events_retention_days: Optional[int] = None,
    ):
        """
        Manually trigger the archive retention cleanup (also runs automatically
        once a day, see _archive_cleanup_loop()). Deletes daily_reports/articles/
        briefing_narratives/narrative audio files/editorial_perspectives/
        editorial_watch_next/generation_runs older than retention_days (defaults
        to ARCHIVE_RETENTION_DAYS, currently 7), plus product_events older than
        product_events_retention_days (defaults to PRODUCT_EVENTS_RETENTION_DAYS,
        currently 90 — a separate, longer window since analytics has no other
        bound anywhere else in the codebase). Irreversible — there is no
        backup step. saved_articles are never touched (independent copy, see
        app/retention/service.py).
        """
        require_admin_key(x_admin_key)
        _log(
            "admin_archive_cleanup_triggered",
            retention_days=retention_days,
            product_events_retention_days=product_events_retention_days,
        )
        try:
            stats = run_archive_cleanup(retention_days, product_events_retention_days)
        except ValueError as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")
        except Exception as e:
            _log("archive_cleanup_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Archive cleanup error. Please try again.")
        return {"status": "ok", **stats}

    @app.post("/admin/run-pipeline")
    def admin_run_pipeline(x_admin_key: Optional[str] = Header(default=None)):
        """
        Run the full pipeline in one call: ingest → assemble → generate.

        Reuses the same orchestration function as the scheduler.  Returns
        structured stats for each step so the caller can inspect results.
        Sends a push notification on success, same as the scheduler.
        """
        require_admin_key(x_admin_key)
        _log("admin_pipeline_triggered")
        stats = run_scheduled_pipeline()
        push_start = time.perf_counter()
        _notify_after_pipeline(stats)
        push_seconds = round(time.perf_counter() - push_start, 2)
        stats.setdefault("timing_seconds", {})["push"] = push_seconds
        stats["timing_seconds"]["total"] = round(
            stats["timing_seconds"].get("total", 0) + push_seconds,
            2,
        )
        return stats

    @app.post("/admin/test-push")
    def admin_test_push(
        body: dict,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Send a test push notification to all registered devices.
        Payload: {"title": "...", "body": "...", "data": {"url": "...", "topic": "..."}}
        `data` is optional — pass it to test the mobile app's notification-tap
        deep link (see the notification notes in docs/ENGINEERING.md).
        Protected by ADMIN_API_KEY.
        """
        require_admin_key(x_admin_key)

        title = (body.get("title") or "").strip() or "WhatsNews"
        push_body = (body.get("body") or "").strip() or "Your daily briefing is ready."
        push_data = body.get("data") if isinstance(body.get("data"), dict) else None

        result = _send_push_to_all_devices(title, push_body, push_data)

        if result["status"] == "error":
            raise HTTPException(status_code=502, detail=result["detail"])

        return result
