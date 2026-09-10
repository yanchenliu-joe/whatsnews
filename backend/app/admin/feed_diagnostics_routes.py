"""Admin feed reliability/ingestion diagnostics routes."""

from __future__ import annotations

from typing import Optional

import psycopg2
from fastapi import FastAPI, Header, HTTPException

from app.admin.feed_scoring import (
    _compute_feed_quality_score,
    _compute_topic_health_score,
    _feed_health_status,
    _feed_reliability_score,
)
from app.database import get_connection
from app.ingestion import get_latest_ingestion_run
from app.log_utils import _log


def register_admin_feed_diagnostics_routes(app: FastAPI, require_admin_key) -> None:
    """Attach /admin/feed-health, /admin/rss-scale-audit*, /admin/latest-ingestion-run.
    require_admin_key is app.admin.deps.require_admin_key."""

    @app.get("/admin/feed-health")
    def admin_feed_health(x_admin_key: Optional[str] = Header(default=None)):
        """
        Per-feed reliability summary grouped by topic.
        Includes feed quality scores (0–100), topic health scores (0–100), and
        status classification: healthy / warning / failed.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            # Main feed rows
            cur.execute(
                """
                SELECT
                    ns.id,
                    t.id    AS topic_id,
                    t.name  AS topic,
                    t.sort_order,
                    ns.name AS source,
                    ns.feed_url,
                    ns.is_active,
                    COALESCE(ns.failure_count, 0)         AS failure_count,
                    COALESCE(ns.success_count, 0)         AS success_count,
                    COALESCE(ns.consecutive_failures, 0)  AS consecutive_failures,
                    COALESCE(ns.consecutive_successes, 0) AS consecutive_successes,
                    ns.last_success_at,
                    ns.last_failure_at,
                    ns.auto_disabled_at
                FROM news_sources ns
                JOIN topics t ON t.id = ns.topic_id
                ORDER BY t.sort_order ASC, t.name ASC, ns.consecutive_failures DESC
                """
            )
            rows = [dict(r) for r in cur.fetchall()]

            # Recent article counts per topic (last 7 days) for topic health scoring
            cur.execute(
                """
                SELECT t.id AS topic_id, COUNT(a.id) AS recent_article_count
                FROM topics t
                LEFT JOIN daily_reports dr
                    ON dr.topic_id = t.id
                   AND dr.report_date >= CURRENT_DATE - INTERVAL '7 days'
                LEFT JOIN articles a ON a.report_id = dr.id
                GROUP BY t.id
                """
            )
            article_counts: dict[int, int] = {
                r["topic_id"]: (r["recent_article_count"] or 0)
                for r in cur.fetchall()
            }

            cur.close()
            conn.close()

            # Annotate each feed with status, reliability_score, quality_score
            for r in rows:
                r["status"] = _feed_health_status(r)
                r["reliability_score"] = _feed_reliability_score(r)
                r["quality_score"] = _compute_feed_quality_score(r)
                r["last_success_time"] = r["last_success_at"].isoformat() if r["last_success_at"] else None
                r["last_failure_time"] = r["last_failure_at"].isoformat() if r["last_failure_at"] else None
                r["auto_disabled_at"] = r["auto_disabled_at"].isoformat() if r["auto_disabled_at"] else None

            # Group by topic
            topics_map: dict[int, dict] = {}
            for r in rows:
                tid = r["topic_id"]
                if tid not in topics_map:
                    topics_map[tid] = {
                        "topic_name": r["topic"],
                        "topic_id": tid,
                        "total": 0,
                        "active": 0,
                        "disabled": 0,
                        "healthy": 0,
                        "warning": 0,
                        "failed": 0,
                        "feeds": [],
                    }
                grp = topics_map[tid]
                grp["total"] += 1
                if r["is_active"]:
                    grp["active"] += 1
                else:
                    grp["disabled"] += 1
                grp[r["status"]] += 1
                grp["feeds"].append({
                    "id": r["id"],
                    "name": r["source"],
                    "feed_url": r["feed_url"],
                    "is_active": r["is_active"],
                    "status": r["status"],
                    "reliability_score": r["reliability_score"],
                    "quality_score": r["quality_score"],
                    "failure_count": r["failure_count"],
                    "success_count": r["success_count"],
                    "consecutive_failures": r["consecutive_failures"],
                    "consecutive_successes": r["consecutive_successes"],
                    "last_success_time": r["last_success_time"],
                    "last_failure_time": r["last_failure_time"],
                    "auto_disabled_at": r["auto_disabled_at"],
                })

            # Attach topic health score to each group
            for tid, grp in topics_map.items():
                recent_articles = article_counts.get(tid, 0)
                grp["recent_article_count_7d"] = recent_articles
                grp["topic_health_score"] = _compute_topic_health_score(grp, recent_articles)

            topics_list = list(topics_map.values())
            total_feeds = len(rows)
            active_feeds = sum(1 for r in rows if r["is_active"])
            n_healthy = sum(1 for r in rows if r["status"] == "healthy")
            n_warning = sum(1 for r in rows if r["status"] == "warning")
            n_failed = sum(1 for r in rows if r["status"] == "failed")

            # Quality score summary
            all_quality = [r["quality_score"]["total"] for r in rows]
            stable_count = sum(1 for r in rows if r["quality_score"]["classification"] == "stable")
            medium_risk_count = sum(1 for r in rows if r["quality_score"]["classification"] == "medium_risk")
            removal_candidate_count = sum(1 for r in rows if r["quality_score"]["classification"] == "candidate_for_removal")
            avg_quality = round(sum(all_quality) / len(all_quality)) if all_quality else 0

            return {
                "summary": {
                    "total_feeds": total_feeds,
                    "active_feeds": active_feeds,
                    "disabled_feeds": total_feeds - active_feeds,
                    "healthy_feeds": n_healthy,
                    "warning_feeds": n_warning,
                    "failed_feeds": n_failed,
                    "quality_score_avg": avg_quality,
                    "quality_stable_count": stable_count,
                    "quality_medium_risk_count": medium_risk_count,
                    "quality_removal_candidate_count": removal_candidate_count,
                },
                "topics": topics_list,
            }
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/rss-scale-audit")
    def admin_rss_scale_audit(x_admin_key: Optional[str] = Header(default=None)):
        """
        Validates actual DB state of the feed registry.
        Reports total counts, per-topic distribution, duplicate URLs, and data quality issues.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            # 1. Overall counts
            cur.execute(
                """
                SELECT
                    COUNT(*)                                       AS total_feeds,
                    COUNT(*) FILTER (WHERE is_active = TRUE)      AS active_feeds,
                    COUNT(*) FILTER (WHERE is_active = FALSE)     AS disabled_feeds
                FROM news_sources
                """
            )
            counts = dict(cur.fetchone())

            # 2. Per-topic breakdown
            cur.execute(
                """
                SELECT
                    t.id, t.name, t.sort_order, t.is_active AS topic_active,
                    COUNT(ns.id)                                   AS feed_count,
                    COUNT(ns.id) FILTER (WHERE ns.is_active)       AS active_feed_count,
                    COUNT(ns.id) FILTER (WHERE NOT ns.is_active)   AS disabled_feed_count
                FROM topics t
                LEFT JOIN news_sources ns ON ns.topic_id = t.id
                GROUP BY t.id, t.name, t.sort_order, t.is_active
                ORDER BY t.sort_order ASC
                """
            )
            topics_rows = [dict(r) for r in cur.fetchall()]

            # 3. Duplicate feed_url detection (same URL across any topics or duplicated in one)
            cur.execute(
                """
                SELECT ns.feed_url,
                       COUNT(*) AS occurrences,
                       array_agg(DISTINCT t.name ORDER BY t.name) AS topics
                FROM news_sources ns
                JOIN topics t ON t.id = ns.topic_id
                GROUP BY ns.feed_url
                HAVING COUNT(*) > 1
                ORDER BY occurrences DESC
                """
            )
            dup_rows = [dict(r) for r in cur.fetchall()]

            # 4. Feeds with null/empty URL
            cur.execute(
                "SELECT id, name, topic_id FROM news_sources WHERE feed_url IS NULL OR TRIM(feed_url) = ''"
            )
            missing_url = [dict(r) for r in cur.fetchall()]

            # 5. Feeds with null/empty name
            cur.execute(
                "SELECT id, feed_url, topic_id FROM news_sources WHERE name IS NULL OR TRIM(name) = ''"
            )
            missing_name = [dict(r) for r in cur.fetchall()]

            # 6. Feeds not linked to any topic (topic_id is NULL — shouldn't happen due to FK)
            cur.execute("SELECT id, name, feed_url FROM news_sources WHERE topic_id IS NULL")
            missing_topic = [dict(r) for r in cur.fetchall()]

            cur.close()
            conn.close()

            duplicate_feed_urls = [
                {
                    "feed_url": r["feed_url"],
                    "occurrences": r["occurrences"],
                    "topics": list(r["topics"]),
                }
                for r in dup_rows
            ]

            return {
                "total_feeds": counts["total_feeds"],
                "active_feeds": counts["active_feeds"],
                "disabled_feeds": counts["disabled_feeds"],
                "topics": [
                    {
                        "topic_id": r["id"],
                        "topic_name": r["name"],
                        "topic_active": r["topic_active"],
                        "feed_count": r["feed_count"],
                        "active_feed_count": r["active_feed_count"],
                        "disabled_feed_count": r["disabled_feed_count"],
                    }
                    for r in topics_rows
                ],
                "duplicate_feed_urls": duplicate_feed_urls,
                "feeds_missing_topic": missing_topic,
                "feeds_missing_url": missing_url,
                "feeds_missing_name": missing_name,
                "data_quality_ok": (
                    len(duplicate_feed_urls) == 0
                    and len(missing_url) == 0
                    and len(missing_name) == 0
                    and len(missing_topic) == 0
                ),
            }
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/admin/rss-scale-audit/bottlenecks")
    def admin_rss_bottlenecks(x_admin_key: Optional[str] = Header(default=None)):
        """
        Bottleneck report derived from the latest ingestion run + DB failure history.
        Reports: slowest 10 feeds, most frequently failing 10 feeds, highest dedup-rate feeds.
        Requires at least one POST /admin/ingest to have run since server start.
        """
        require_admin_key(x_admin_key)

        # Section 1: Per-feed metrics from DB (most failing)
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    ns.id,
                    t.name  AS topic,
                    ns.name AS source,
                    ns.feed_url,
                    ns.is_active,
                    COALESCE(ns.failure_count, 0)        AS failure_count,
                    COALESCE(ns.success_count, 0)        AS success_count,
                    COALESCE(ns.consecutive_failures, 0) AS consecutive_failures,
                    ns.last_failure_at,
                    ns.auto_disabled_at
                FROM news_sources ns
                JOIN topics t ON t.id = ns.topic_id
                WHERE ns.failure_count > 0 OR ns.consecutive_failures > 0
                ORDER BY ns.consecutive_failures DESC, ns.failure_count DESC
                LIMIT 10
                """
            )
            db_failing = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()
        except Exception:
            db_failing = []

        # Section 2: From latest ingestion run (slowest + highest dedup rate)
        run = get_latest_ingestion_run()
        source_timings: list[dict] = []
        if run:
            source_timings = run.get("source_timings") or []

        # Slowest 10 by fetch duration
        slowest_10 = sorted(
            source_timings,
            key=lambda t: t.get("duration_seconds") or t.get("seconds") or 0,
            reverse=True,
        )[:10]

        # Highest dedup rate: skipped / max(1, fetched)
        dedup_candidates = [
            t for t in source_timings
            if (t.get("fetched") or 0) > 0
        ]
        dedup_candidates.sort(
            key=lambda t: (t.get("skipped") or 0) / max(1, t.get("fetched") or 1),
            reverse=True,
        )
        highest_dedup_10 = [
            {
                "topic": t.get("topic"),
                "source": t.get("source"),
                "feed_url": t.get("feed_url"),
                "fetched": t.get("fetched", 0),
                "skipped": t.get("skipped", 0),
                "inserted": t.get("inserted", 0),
                "dedup_rate_pct": round(
                    100 * (t.get("skipped") or 0) / max(1, t.get("fetched") or 1), 1
                ),
            }
            for t in dedup_candidates[:10]
        ]

        # Failed feeds from latest run
        failed_in_run = [
            {
                "topic": t.get("topic"),
                "source": t.get("source"),
                "feed_url": t.get("feed_url"),
                "status": t.get("status"),
                "error": t.get("error_message"),
                "duration_seconds": t.get("duration_seconds") or t.get("seconds"),
            }
            for t in source_timings
            if t.get("status") != "ok"
        ]

        return {
            "run_available": run is not None,
            "run_started_at": run.get("started_at") if run else None,
            "slowest_10_feeds": [
                {
                    "topic": t.get("topic"),
                    "source": t.get("source"),
                    "feed_url": t.get("feed_url"),
                    "duration_seconds": t.get("duration_seconds") or t.get("seconds"),
                    "status": t.get("status"),
                    "fetched": t.get("fetched", 0),
                    "inserted": t.get("inserted", 0),
                }
                for t in slowest_10
            ],
            "most_failing_10_feeds_db": [
                {
                    "id": r["id"],
                    "topic": r["topic"],
                    "source": r["source"],
                    "feed_url": r["feed_url"],
                    "is_active": r["is_active"],
                    "failure_count": r["failure_count"],
                    "success_count": r["success_count"],
                    "consecutive_failures": r["consecutive_failures"],
                    "last_failure_at": r["last_failure_at"].isoformat() if r.get("last_failure_at") else None,
                    "auto_disabled": r["auto_disabled_at"] is not None,
                }
                for r in db_failing
            ],
            "highest_dedup_rate_10_feeds": highest_dedup_10,
            "failed_feeds_in_last_run": failed_in_run,
        }

    @app.get("/admin/latest-ingestion-run")
    def admin_latest_ingestion_run(x_admin_key: Optional[str] = Header(default=None)):
        """
        Returns metrics from the most recent ingest_all_active_sources() call.
        Resets to null on server restart. Trigger POST /admin/ingest to populate.
        """
        require_admin_key(x_admin_key)
        run = get_latest_ingestion_run()
        if run is None:
            return {"available": False, "message": "No ingestion run recorded since server start."}

        # Compute stability metrics from source_timings
        source_timings: list[dict] = run.get("source_timings") or []
        feeds_checked = run.get("feeds_checked") or len(source_timings)
        feeds_success = run.get("feeds_success", 0)
        feeds_failed = run.get("feeds_failed", 0)
        feed_success_rate_pct = round(100 * feeds_success / max(1, feeds_checked), 1)

        articles_fetched = run.get("articles_fetched", 0)
        semantic_skipped = run.get("semantic_duplicates_skipped", 0)
        hard_skipped = run.get("hard_duplicates_skipped", 0)
        total_skipped = semantic_skipped + hard_skipped
        dedup_rate_pct = round(100 * total_skipped / max(1, articles_fetched + total_skipped), 1)

        # Timing breakdown
        fetch_s = run.get("fetch_phase_seconds") or 0
        persist_s = run.get("persist_phase_seconds") or 0
        build_s = round(run.get("build_records_seconds") or 0, 2)
        db_s = round(run.get("db_insert_seconds") or 0, 2)

        # Per-topic timing summary
        topic_seconds = run.get("topic_seconds") or {}
        topic_timing_summary = [
            {"topic": k, "duration_seconds": v}
            for k, v in sorted(topic_seconds.items(), key=lambda x: x[1], reverse=True)
        ]

        # Stability constraint checks
        target_duration_s = 120
        stability_checks = {
            "completed_within_120s": (run.get("duration_seconds") or 0) <= target_duration_s,
            "feed_failure_rate_under_20pct": (
                (100 - feed_success_rate_pct) < 20 if feeds_checked > 0 else True
            ),
            "semantic_dedup_rate_10_to_40pct": (
                10 <= dedup_rate_pct <= 40 if articles_fetched > 0 else None
            ),
        }

        return {
            "available": True,
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "duration_seconds": run.get("duration_seconds"),
            "stability_target_seconds": target_duration_s,
            "stability_checks": stability_checks,
            "feeds": {
                "checked": feeds_checked,
                "success": feeds_success,
                "failed": feeds_failed,
                "success_rate_pct": feed_success_rate_pct,
            },
            "articles": {
                "fetched": articles_fetched,
                "inserted": run.get("articles_inserted", 0),
                "skipped_total": total_skipped,
                "hard_duplicates_skipped": hard_skipped,
                "semantic_duplicates_skipped": semantic_skipped,
                "dedup_rate_pct": dedup_rate_pct,
            },
            "topics_processed": run.get("topics_processed", 0),
            "errors_count": run.get("errors_count", 0),
            "failed_feeds": run.get("failed_feeds", []),
            "semantic_dedup": {
                "threshold": 0.82,
                "semantic_duplicates_skipped": semantic_skipped,
                "sample_duplicates": run.get("semantic_sample_duplicates", []),
            },
            "performance": {
                "total_seconds": run.get("duration_seconds"),
                "fetch_phase_seconds": fetch_s,
                "persist_phase_seconds": persist_s,
                "build_records_seconds": build_s,
                "db_insert_seconds": db_s,
            },
            "topic_timing": topic_timing_summary,
            "slow_sources": run.get("slow_sources", []),
        }
