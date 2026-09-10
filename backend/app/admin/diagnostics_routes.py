"""Read-only admin diagnostics/audit routes."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
from fastapi import FastAPI, Header, HTTPException

from app.assembly import compute_importance_score, passes_relevance_filter
from app.database import get_connection
from app.log_utils import _log
from app.pipeline.scheduler import seconds_until_next_run


def register_admin_diagnostics_routes(app: FastAPI, require_admin_key) -> None:
    """Attach read-only /admin/* diagnostics endpoints. require_admin_key is app.admin.deps.require_admin_key."""

    @app.get("/admin/system-status")
    def admin_system_status(x_admin_key: Optional[str] = Header(default=None)):
        """
        Returns scheduler configuration, current server time, and the last
        successful and failed generation runs.
        """
        require_admin_key(x_admin_key)

        daily_time = os.getenv("SCHEDULER_DAILY_TIME")
        scheduler_enabled = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"

        if daily_time:
            scheduler_mode = "daily"
            timezone = os.getenv("SCHEDULER_TIMEZONE", "UTC")
            next_run_str = None
            if scheduler_enabled:
                daily_times = [t.strip() for t in daily_time.split(",") if t.strip()]
                _, next_run = seconds_until_next_run(daily_times, timezone)
                next_run_str = next_run.isoformat()
        else:
            scheduler_mode = "interval"
            timezone = None
            next_run_str = None

        server_time = datetime.now(tz=ZoneInfo("UTC")).isoformat()

        last_success = None
        last_failure = None

        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT id, topic, trigger_type, started_at, duration_ms, articles_count
                FROM generation_runs
                WHERE status = 'success'
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                last_success = {
                    "id": row["id"],
                    "topic": row["topic"],
                    "trigger_type": row["trigger_type"],
                    "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                    "duration_ms": row["duration_ms"],
                    "articles_count": row["articles_count"],
                }

            cur.execute(
                """
                SELECT id, topic, trigger_type, started_at, error_message
                FROM generation_runs
                WHERE status = 'failed'
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                last_failure = {
                    "id": row["id"],
                    "topic": row["topic"],
                    "trigger_type": row["trigger_type"],
                    "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                    "error_message": row["error_message"],
                }

            cur.close()
            conn.close()
        except Exception as exc:
            # DB not configured or generation_runs not yet migrated — status
            # still returns (last_success/last_failure stay None), but this
            # is now logged rather than silently swallowed (Technical Debt
            # #10) so a fresh deploy missing the migration is diagnosable
            # from server logs instead of just looking like "no runs yet".
            _log(
                "generation_runs_query_unavailable",
                error=str(exc)[:200],
                note="Apply schema.sql's generation_runs migration if this persists",
            )

        return {
            "server_time": server_time,
            "scheduler_enabled": scheduler_enabled,
            "scheduler_mode": scheduler_mode,
            "scheduler_daily_time": daily_time,
            "scheduler_timezone": timezone,
            "next_scheduled_run": next_run_str,
            "last_successful_run": last_success,
            "last_failed_run": last_failure,
        }

    @app.get("/admin/generation-runs")
    def admin_generation_runs(
        topic: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Returns recent generation runs, newest first.
        Optional filters: ?topic=, ?status=running|success|failed, ?limit=N (default 20).
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            query = """
                SELECT id, topic, trigger_type, status, report_date,
                       started_at, finished_at, duration_ms, articles_count,
                       ai_refine_attempted, ai_refine_success_count,
                       ai_refine_fallback_count, error_message
                FROM generation_runs
                WHERE 1=1
            """
            params: list = []

            if topic:
                query += " AND topic = %s"
                params.append(topic)
            if status:
                query += " AND status = %s"
                params.append(status)

            query += " ORDER BY started_at DESC LIMIT %s"
            params.append(max(1, min(limit, 100)))

            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            return [
                {
                    "id": r["id"],
                    "topic": r["topic"],
                    "trigger_type": r["trigger_type"],
                    "status": r["status"],
                    "report_date": str(r["report_date"]) if r["report_date"] else None,
                    "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                    "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
                    "duration_ms": r["duration_ms"],
                    "articles_count": r["articles_count"],
                    "ai_refine_attempted": r["ai_refine_attempted"],
                    "ai_refine_success_count": r["ai_refine_success_count"],
                    "ai_refine_fallback_count": r["ai_refine_fallback_count"],
                    "error_message": r["error_message"],
                }
                for r in rows
            ]

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/topic-status")
    def admin_topic_status(x_admin_key: Optional[str] = Header(default=None)):
        """
        Returns a per-topic summary: latest report date, latest run status and time,
        and article count from the most recent run.
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except Exception as e:
            _log("database_connection_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database connection error. Please try again.")

        try:
            cur = conn.cursor()

            # Get all topics (admin sees all, including inactive).
            cur.execute(
                "SELECT name, is_active FROM topics ORDER BY sort_order ASC, name ASC"
            )
            topic_rows = [dict(r) for r in cur.fetchall()]

            result = []
            for topic_row in topic_rows:
                topic_name = topic_row["name"]
                # Latest daily report date for this topic.
                cur.execute(
                    """
                    SELECT dr.report_date
                    FROM daily_reports dr
                    JOIN topics t ON t.id = dr.topic_id
                    WHERE t.name = %s
                    ORDER BY dr.report_date DESC
                    LIMIT 1
                    """,
                    (topic_name,),
                )
                dr = cur.fetchone()

                # Latest generation run for this topic.
                cur.execute(
                    """
                    SELECT status, started_at, articles_count
                    FROM generation_runs
                    WHERE topic = %s
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (topic_name,),
                )
                run = cur.fetchone()

                result.append({
                    "topic": topic_name,
                    "is_active": topic_row["is_active"],
                    "latest_report_date": str(dr["report_date"]) if dr else None,
                    "latest_run_status": run["status"] if run else None,
                    "latest_run_time": run["started_at"].isoformat() if run and run["started_at"] else None,
                    "latest_run_articles_count": run["articles_count"] if run else None,
                })

            cur.close()
            conn.close()
            return result

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/briefing-quality-audit")
    def admin_briefing_quality_audit(x_admin_key: Optional[str] = Header(default=None)):
        """
        Read-only quality audit of the latest daily report for every active topic.
        Computes is_strict_match via passes_relevance_filter (same logic as assembly).

        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name FROM topics WHERE is_active = TRUE ORDER BY sort_order ASC, name ASC"
            )
            topic_rows = [dict(r) for r in cur.fetchall()]

            topics_out = []
            for topic_row in topic_rows:
                topic_name = topic_row["name"]
                cur.execute(
                    """
                    SELECT id, report_date
                    FROM daily_reports
                    WHERE topic_id = %s
                    ORDER BY report_date DESC
                    LIMIT 1
                    """,
                    (topic_row["id"],),
                )
                report = cur.fetchone()
                if not report:
                    topics_out.append({
                        "topic": topic_name,
                        "report_date": None,
                        "articles": [],
                    })
                    continue

                report_date = str(report["report_date"])
                cur.execute(
                    """
                    SELECT title, source, url, raw_url, published_at,
                           COALESCE(summary, '') AS summary,
                           why_it_matters
                    FROM articles
                    WHERE report_id = %s
                    ORDER BY id ASC
                    """,
                    (report["id"],),
                )
                articles = []
                for row in cur.fetchall():
                    a = dict(row)
                    summary = a.get("summary") or ""
                    articles.append({
                        "topic": topic_name,
                        "report_date": report_date,
                        "title": a["title"],
                        "source": a["source"],
                        "url": a["url"],
                        "raw_url": a["raw_url"],
                        "published_at": a["published_at"].isoformat() if a["published_at"] else None,
                        "summary": summary,
                        "why_it_matters": a["why_it_matters"],
                        "is_strict_match": passes_relevance_filter(
                            a["title"], summary, topic_name
                        ),
                    })

                topics_out.append({
                    "topic": topic_name,
                    "report_date": report_date,
                    "articles": articles,
                })

            cur.close()
            conn.close()
            return {"topics": topics_out}

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/report-debug")
    def admin_report_debug(
        topic: str,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Debug view of the most recent report for a topic.
        Returns report metadata and per-article detail (including dates,
        source, and why_it_matters) for quick quality inspection.

        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            cur.execute("SELECT id, name FROM topics WHERE name = %s", (topic,))
            topic_row = cur.fetchone()
            if not topic_row:
                cur.close()
                conn.close()
                raise HTTPException(status_code=404, detail=f"Topic '{topic}' not found.")

            cur.execute(
                """
                SELECT id, report_date
                FROM daily_reports
                WHERE topic_id = %s
                ORDER BY report_date DESC
                LIMIT 1
                """,
                (topic_row["id"],),
            )
            report = cur.fetchone()
            if not report:
                cur.close()
                conn.close()
                raise HTTPException(
                    status_code=404,
                    detail=f"No daily report found for topic '{topic}'.",
                )

            cur.execute(
                """
                SELECT id, title, source, url,
                       published_at, fetched_at, why_it_matters
                FROM articles
                WHERE report_id = %s
                ORDER BY COALESCE(published_at, fetched_at) DESC NULLS LAST, id DESC
                """,
                (report["id"],),
            )
            articles = [dict(r) for r in cur.fetchall()]

            cur.close()
            conn.close()

            _topic_name = topic_row["name"]
            articles.sort(
                key=lambda a: compute_importance_score(a["title"], a.get("summary") or "", _topic_name),
                reverse=True,
            )

            return {
                "topic": _topic_name,
                "report_id": report["id"],
                "report_date": str(report["report_date"]),
                "item_count": len(articles),
                "items": [
                    {
                        "id": a["id"],
                        "title": a["title"],
                        "source": a["source"],
                        "url": a["url"],
                        "published_at": a["published_at"].isoformat() if a["published_at"] else None,
                        "fetched_at": a["fetched_at"].isoformat() if a["fetched_at"] else None,
                        "why_it_matters": a["why_it_matters"],
                        "importance_score": compute_importance_score(a["title"], a.get("summary") or "", _topic_name),
                    }
                    for a in articles
                ],
            }

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/events-summary")
    def admin_events_summary(x_admin_key: Optional[str] = Header(default=None)):
        """
        Lightweight analytics view: event counts (last 24h) and recent events.
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT event_name, COUNT(*) AS cnt
                FROM product_events
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                GROUP BY event_name
                ORDER BY cnt DESC
                """
            )
            counts_rows = cur.fetchall()

            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM product_events
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                """
            )
            total_24h = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT id, event_name, article_id, topic_name, metadata_text, created_at
                FROM product_events
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
            recent = cur.fetchall()

            cur.close()
            conn.close()

            counts = {r["event_name"]: r["cnt"] for r in counts_rows}
            opened = counts.get("article_opened", 0)
            saved = counts.get("article_saved", 0)
            pushes = counts.get("push_sent", 0)
            refreshes = counts.get("briefing_refreshed", 0)

            metrics = {
                "save_rate": round(saved / opened, 2) if opened else None,
                "opens_per_push": round(opened / pushes, 1) if pushes else None,
                "opens_per_refresh": round(opened / refreshes, 1) if refreshes else None,
            }

            return {
                "total_24h": total_24h,
                "counts": counts,
                "metrics": metrics,
                "recent": [
                    {
                        "id": r["id"],
                        "event_name": r["event_name"],
                        "article_id": r["article_id"],
                        "topic_name": r["topic_name"],
                        "metadata_text": r["metadata_text"],
                        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    }
                    for r in recent
                ],
            }

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/topics")
    def admin_get_topics(x_admin_key: Optional[str] = Header(default=None)):
        """
        Returns all topics including inactive ones, for admin/debug use.
        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, is_active, sort_order, created_at
                FROM topics
                ORDER BY sort_order ASC, name ASC
                """
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "is_active": r["is_active"],
                    "sort_order": r["sort_order"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")
