"""Admin feed recommendation + topic rebalancing routes (advisory, read-only)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
from fastapi import FastAPI, Header, HTTPException

from app.admin.feed_scoring import _compute_feed_quality_score
from app.database import get_connection
from app.log_utils import _log


def register_admin_feed_recommendation_routes(app: FastAPI, require_admin_key) -> None:
    """Attach /admin/feed-recommendations and /admin/topic-rebalancing.
    require_admin_key is app.admin.deps.require_admin_key."""

    @app.get("/admin/feed-recommendations")
    def admin_feed_recommendations(x_admin_key: Optional[str] = Header(default=None)):
        """
        Automated feed recommendation engine.
        Classifies feeds into: to_disable, to_replace, to_promote, underperforming, high_value.
        All recommendations are advisory — no feeds are modified by this endpoint.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            # Fetch all feeds with reliability + lifecycle data
            cur.execute(
                """
                SELECT
                    ns.id,
                    t.name                                AS topic,
                    ns.name                               AS source,
                    ns.feed_url,
                    ns.is_active,
                    COALESCE(ns.feed_state, 'active')     AS feed_state,
                    COALESCE(ns.failure_count, 0)         AS failure_count,
                    COALESCE(ns.success_count, 0)         AS success_count,
                    COALESCE(ns.consecutive_failures, 0)  AS consecutive_failures,
                    ns.last_success_at,
                    ns.last_failure_at,
                    ns.replace_flag,
                    ns.replace_reason
                FROM news_sources ns
                JOIN topics t ON t.id = ns.topic_id
                WHERE ns.is_active = TRUE
                ORDER BY ns.failure_count DESC, ns.consecutive_failures DESC
                """
            )
            feeds = [dict(r) for r in cur.fetchall()]

            # Article contribution per source in last 30 days
            cur.execute(
                """
                SELECT a.source, t.name AS topic, COUNT(a.id) AS article_count
                FROM articles a
                JOIN daily_reports dr ON dr.id = a.report_id
                JOIN topics t ON t.id = dr.topic_id
                WHERE dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY a.source, t.name
                """
            )
            source_article_counts: dict[tuple, int] = {
                (r["source"], r["topic"]): r["article_count"]
                for r in cur.fetchall()
            }

            # Total article count per topic in last 30 days
            cur.execute(
                """
                SELECT t.name AS topic, COUNT(a.id) AS total
                FROM articles a
                JOIN daily_reports dr ON dr.id = a.report_id
                JOIN topics t ON t.id = dr.topic_id
                WHERE dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY t.name
                """
            )
            topic_totals: dict[str, int] = {r["topic"]: r["total"] for r in cur.fetchall()}

            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        now = datetime.now(tz=ZoneInfo("UTC"))

        def _days_since_success(feed: dict) -> float | None:
            ts = feed.get("last_success_at")
            if not ts:
                return None
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=ZoneInfo("UTC"))
            return (now - ts).total_seconds() / 86400

        def _article_contribution_pct(feed: dict) -> float:
            count = source_article_counts.get((feed["source"], feed["topic"]), 0)
            total = topic_totals.get(feed["topic"], 0)
            if total == 0:
                return 0.0
            return round(100 * count / total, 1)

        to_disable: list[dict] = []
        to_replace: list[dict] = []
        to_promote: list[dict] = []
        underperforming: list[dict] = []
        high_value: list[dict] = []

        for f in feeds:
            qs = _compute_feed_quality_score(f)
            q = qs["total"]
            days_since = _days_since_success(f)
            contrib_pct = _article_contribution_pct(f)
            failure_count = f["failure_count"]
            consecutive_failures = f["consecutive_failures"]

            row = {
                "id": f["id"],
                "topic": f["topic"],
                "source": f["source"],
                "feed_url": f["feed_url"],
                "feed_state": f["feed_state"],
                "quality_score": q,
                "failure_count": failure_count,
                "consecutive_failures": consecutive_failures,
                "days_since_last_success": round(days_since, 1) if days_since is not None else None,
                "article_contribution_pct_30d": contrib_pct,
            }

            # to_disable: quality < 40 AND failure_count >= 5 AND no success in 7 days
            if q < 40 and failure_count >= 5 and (days_since is None or days_since > 7):
                to_disable.append({**row, "reason": "chronic_failure_no_recent_success"})

            # to_replace: quality < 50 AND low article contribution (< 2% of topic)
            elif q < 50 and contrib_pct < 2.0:
                replacement_type = (
                    "mainstream"    if "mainstream" in f["source"].lower()
                    else "industry" if contrib_pct == 0.0
                    else "fast_breaking"
                )
                to_replace.append({
                    **row,
                    "reason": "low_quality_low_contribution",
                    "suggested_replacement_type": replacement_type,
                })

            # to_promote: quality > 85 AND stable 7+ days
            elif q > 85 and (days_since is not None and days_since <= 7) and consecutive_failures == 0:
                to_promote.append({**row, "reason": "high_quality_stable"})

            # underperforming: quality < 60
            if q < 60 and f not in to_disable:
                underperforming.append(row)

            # high_value: quality > 90
            if q > 90:
                high_value.append(row)

        return {
            "generated_at": now.isoformat(),
            "summary": {
                "to_disable_count": len(to_disable),
                "to_replace_count": len(to_replace),
                "to_promote_count": len(to_promote),
                "underperforming_count": len(underperforming),
                "high_value_count": len(high_value),
            },
            "to_disable": to_disable,
            "to_replace": to_replace,
            "to_promote": to_promote,
            "underperforming_feeds": underperforming,
            "high_value_feeds": high_value,
        }

    @app.get("/admin/topic-rebalancing")
    def admin_topic_rebalancing(x_admin_key: Optional[str] = Header(default=None)):
        """
        Topic feed diversity analysis.
        Detects source domination (> 40% of topic articles from one source),
        feed count imbalance, and underrepresented topic categories.
        Advisory only — no changes are made.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()

            # Feed count per topic
            cur.execute(
                """
                SELECT t.id, t.name AS topic, t.sort_order,
                       COUNT(ns.id)                              AS total_feeds,
                       COUNT(ns.id) FILTER (WHERE ns.is_active) AS active_feeds,
                       COUNT(ns.id) FILTER (
                           WHERE ns.is_active
                             AND COALESCE(ns.feed_state,'active') = 'active'
                       )                                        AS healthy_feeds
                FROM topics t
                LEFT JOIN news_sources ns ON ns.topic_id = t.id
                WHERE t.is_active = TRUE
                GROUP BY t.id, t.name, t.sort_order
                ORDER BY t.sort_order ASC
                """
            )
            topic_feeds = [dict(r) for r in cur.fetchall()]

            # Article contribution per source per topic (last 30 days)
            cur.execute(
                """
                SELECT t.name AS topic, a.source,
                       COUNT(a.id) AS source_count,
                       SUM(COUNT(a.id)) OVER (PARTITION BY t.name) AS topic_total
                FROM articles a
                JOIN daily_reports dr ON dr.id = a.report_id
                JOIN topics t ON t.id = dr.topic_id
                WHERE dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY t.name, a.source
                ORDER BY t.name, source_count DESC
                """
            )
            source_rows = [dict(r) for r in cur.fetchall()]

            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        avg_feeds = (
            sum(t["active_feeds"] for t in topic_feeds) / len(topic_feeds)
            if topic_feeds else 0
        )

        # Build per-topic domination analysis
        topic_source_map: dict[str, list[dict]] = {}
        for r in source_rows:
            topic_source_map.setdefault(r["topic"], []).append(r)

        topics_analysis = []
        overrepresented_topics = []
        underrepresented_topics = []

        for tf in topic_feeds:
            topic_name = tf["topic"]
            active_feeds = tf["active_feeds"]
            sources = topic_source_map.get(topic_name, [])
            topic_total = sources[0]["topic_total"] if sources else 0

            # Dominating sources (> 40% of articles)
            dominating = [
                {
                    "source": s["source"],
                    "article_count": s["source_count"],
                    "share_pct": round(100 * s["source_count"] / max(1, topic_total), 1),
                }
                for s in sources
                if topic_total > 0 and (s["source_count"] / topic_total) > 0.40
            ]

            # Feed count imbalance
            feed_imbalance_score = round(abs(active_feeds - avg_feeds) / max(1, avg_feeds) * 100)
            has_low_feeds = active_feeds < max(1, avg_feeds * 0.6)
            has_high_feeds = active_feeds > avg_feeds * 1.6

            topic_entry = {
                "topic": topic_name,
                "active_feeds": active_feeds,
                "healthy_feeds": tf["healthy_feeds"],
                "total_articles_30d": topic_total,
                "feed_imbalance_score": feed_imbalance_score,
                "avg_feeds_across_topics": round(avg_feeds, 1),
                "dominating_sources": dominating,
                "has_source_domination": len(dominating) > 0,
                "has_low_feed_count": has_low_feeds,
                "has_high_feed_count": has_high_feeds,
                "top_sources": [
                    {
                        "source": s["source"],
                        "article_count": s["source_count"],
                        "share_pct": round(100 * s["source_count"] / max(1, topic_total), 1),
                    }
                    for s in sources[:5]
                ],
                "recommendations": [],
            }

            if dominating:
                topic_entry["recommendations"].append(
                    f"Source domination detected: {', '.join(d['source'] for d in dominating)} "
                    f"contributing > 40% of articles. Consider adding diverse sources."
                )
            if has_low_feeds:
                topic_entry["recommendations"].append(
                    f"Low feed count ({active_feeds} vs avg {round(avg_feeds, 1)}). "
                    "Consider adding feeds for better coverage."
                )
            if has_high_feeds:
                topic_entry["recommendations"].append(
                    f"High feed count ({active_feeds} vs avg {round(avg_feeds, 1)}). "
                    "Consider reviewing and pruning low-quality feeds."
                )

            topics_analysis.append(topic_entry)
            if has_low_feeds:
                underrepresented_topics.append(topic_name)
            if len(dominating) > 0:
                overrepresented_topics.append(topic_name)

        return {
            "generated_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
            "summary": {
                "topics_analyzed": len(topics_analysis),
                "avg_feeds_per_topic": round(avg_feeds, 1),
                "topics_with_source_domination": len(overrepresented_topics),
                "topics_with_low_feed_count": len(underrepresented_topics),
                "overrepresented_topics": overrepresented_topics,
                "underrepresented_topics": underrepresented_topics,
            },
            "topics": topics_analysis,
        }
