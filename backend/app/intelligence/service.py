"""
Intelligence service (Phase 25).

Orchestrates signal scoring + event clustering for one topic or all topics.
All computation is in-process — no new DB tables, no pipeline changes.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.database import get_connection
from app.intelligence.scoring import compute_signal_score
from app.intelligence.clustering import cluster_articles


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _safe_close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass


# ── Source reliability map ────────────────────────────────────────────────────

def _load_source_reliability_map() -> dict[str, int]:
    """Map source name → reliability_score (0–100) from news_sources."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name,
                   CASE
                     WHEN COALESCE(failure_count, 0) + COALESCE(success_count, 0) = 0
                     THEN 100
                     ELSE ROUND(
                       100.0 * COALESCE(success_count, 0)
                       / (COALESCE(failure_count, 0) + COALESCE(success_count, 0))
                     )
                   END AS reliability_score
            FROM news_sources
            WHERE is_active = TRUE
            """
        )
        result = {r["name"]: int(r["reliability_score"] or 70) for r in cur.fetchall()}
        cur.close()
        _safe_close(conn)
        return result
    except Exception:
        return {}


# ── Per-topic intelligence ────────────────────────────────────────────────────

def get_daily_intelligence(
    topic: str,
    report_date: date | None = None,
) -> dict:
    """
    Build a signal-scored, event-clustered intelligence report for one topic.

    Reads today's (or specified date's) assembled articles from daily_reports
    and returns them ranked by signal_score, grouped into events.

    Backward compat: does NOT change /daily-report output.
    """
    now = datetime.now(tz=ZoneInfo("UTC"))
    target_date = report_date or now.date()

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dr.id AS report_id, t.id AS topic_id, t.name AS topic_name
            FROM daily_reports dr
            JOIN topics t ON t.id = dr.topic_id
            WHERE t.name = %s AND dr.report_date = %s
            LIMIT 1
            """,
            (topic, target_date),
        )
        report_row = cur.fetchone()

        if not report_row:
            cur.close()
            _safe_close(conn)
            return {
                "topic": topic,
                "report_date": target_date.isoformat(),
                "available": False,
                "message": "No report available for this topic and date.",
            }

        report_id = report_row["report_id"]
        topic_name = report_row["topic_name"]

        cur.execute(
            """
            SELECT id, title, url, summary, body_text, source, why_it_matters,
                   published_at, fetched_at, editorial_metadata, image_url
            FROM articles
            WHERE report_id = %s
            ORDER BY published_at DESC NULLS LAST
            """,
            (report_id,),
        )
        articles = [dict(r) for r in cur.fetchall()]
        cur.close()
        _safe_close(conn)
    except Exception as e:
        _log("intelligence_db_error", topic=topic, error=str(e)[:200])
        raise

    if not articles:
        return {
            "topic": topic_name,
            "report_date": target_date.isoformat(),
            "available": True,
            "signal_summary": {
                "total_articles": 0, "event_count": 0,
                "high_signal_count": 0, "informational_count": 0,
                "noise_count": 0, "noise_ratio": 0.0, "dedup_efficiency": 0.0,
            },
            "events": [],
            "noise_suppressed_count": 0,
        }

    source_reliability = _load_source_reliability_map()

    # Score each article
    for article in articles:
        source = article.get("source") or ""
        rel = source_reliability.get(source, 70)
        scores = compute_signal_score(article, rel, now)
        article.update(scores)

    # Cluster into events
    all_clusters = cluster_articles(articles)

    high    = [c for c in all_clusters if c["signal_tier"] == "high"]
    info    = [c for c in all_clusters if c["signal_tier"] == "informational"]
    noise   = [c for c in all_clusters if c["signal_tier"] == "noise"]

    total   = len(articles)
    n_noise = sum(c["supporting_article_count"] for c in noise)
    n_high  = sum(c["supporting_article_count"] for c in high)
    n_info  = sum(c["supporting_article_count"] for c in info)
    n_events = len(all_clusters)

    dedup_efficiency = round(
        1 - n_events / max(1, total), 2
    ) if total else 0.0

    avg_signal = round(
        sum(a.get("signal_score", 0) for a in articles) / max(1, total), 1
    )

    _log(
        "intelligence_computed",
        topic=topic,
        articles=total,
        events=n_events,
        high=len(high),
        noise=len(noise),
        dedup_efficiency=dedup_efficiency,
        avg_signal=avg_signal,
    )

    return {
        "topic": topic_name,
        "report_date": target_date.isoformat(),
        "available": True,
        "signal_summary": {
            "total_articles": total,
            "event_count": n_events,
            "high_signal_count": n_high,
            "informational_count": n_info,
            "noise_count": n_noise,
            "noise_ratio": round(n_noise / max(1, total), 2),
            "dedup_efficiency": dedup_efficiency,
            "avg_signal_score": avg_signal,
        },
        "events": high + info,
        "noise_suppressed_count": n_noise,
    }


# ── Cross-topic signal metrics (admin) ───────────────────────────────────────

def get_signal_metrics_for_all_topics(target_date: date | None = None) -> dict:
    """
    Compute signal score distribution across all topics for admin observability.
    Queries articles directly (no per-topic intelligence run) to stay fast.
    """
    now = datetime.now(tz=ZoneInfo("UTC"))
    d = target_date or now.date()

    try:
        conn = get_connection()
        cur = conn.cursor()

        # All articles in today's reports + editorial_metadata
        cur.execute(
            """
            SELECT
                t.name     AS topic,
                a.id,
                a.source,
                a.title,
                a.published_at,
                a.editorial_metadata
            FROM articles a
            JOIN daily_reports dr ON dr.id = a.report_id
            JOIN topics t         ON t.id  = dr.topic_id
            WHERE dr.report_date = %s
            ORDER BY t.name, a.published_at DESC NULLS LAST
            """,
            (d,),
        )
        rows = [dict(r) for r in cur.fetchall()]

        # Source reliability
        cur.execute(
            """
            SELECT name,
                   CASE
                     WHEN COALESCE(failure_count,0)+COALESCE(success_count,0)=0 THEN 100
                     ELSE ROUND(100.0*COALESCE(success_count,0)/
                          (COALESCE(failure_count,0)+COALESCE(success_count,0)))
                   END AS reliability_score
            FROM news_sources WHERE is_active = TRUE
            """
        )
        source_reliability = {r["name"]: int(r["reliability_score"] or 70) for r in cur.fetchall()}

        # Top sources (by article volume and quality) overall
        cur.execute(
            """
            SELECT a.source, COUNT(a.id) AS article_count
            FROM articles a
            JOIN daily_reports dr ON dr.id = a.report_id
            WHERE dr.report_date = %s
            GROUP BY a.source
            ORDER BY article_count DESC
            LIMIT 15
            """,
            (d,),
        )
        top_sources_raw = [dict(r) for r in cur.fetchall()]
        cur.close()
        _safe_close(conn)
    except Exception as e:
        _log("signal_metrics_error", error=str(e)[:200])
        raise

    if not rows:
        return {
            "report_date": d.isoformat(),
            "total_articles": 0,
            "topics": [],
            "top_signal_sources": [],
            "overall_noise_ratio": 0.0,
        }

    # Group by topic and score
    topic_groups: dict[str, list[dict]] = {}
    for row in rows:
        topic_groups.setdefault(row["topic"], []).append(row)

    topic_metrics = []
    all_scores: list[int] = []
    all_noise = 0
    all_total = 0

    for topic_name, articles in topic_groups.items():
        scores = []
        high_count = info_count = noise_count = 0
        for a in articles:
            rel = source_reliability.get(a.get("source") or "", 70)
            result = compute_signal_score(a, rel, now)
            s = result["signal_score"]
            scores.append(s)
            all_scores.append(s)
            if result["signal_tier"] == "high":
                high_count += 1
            elif result["signal_tier"] == "informational":
                info_count += 1
            else:
                noise_count += 1

        all_noise  += noise_count
        all_total  += len(articles)
        avg_s = round(sum(scores) / max(1, len(scores)), 1)
        noise_ratio = round(noise_count / max(1, len(articles)), 2)

        topic_metrics.append({
            "topic": topic_name,
            "article_count": len(articles),
            "avg_signal_score": avg_s,
            "high_signal_count": high_count,
            "informational_count": info_count,
            "noise_count": noise_count,
            "noise_ratio": noise_ratio,
        })

    topic_metrics.sort(key=lambda t: t["avg_signal_score"], reverse=True)

    # Enrich top sources with reliability
    top_sources = [
        {
            "source": s["source"],
            "article_count": s["article_count"],
            "reliability_score": source_reliability.get(s["source"], 70),
        }
        for s in top_sources_raw
    ]

    overall_avg = round(sum(all_scores) / max(1, len(all_scores)), 1) if all_scores else 0

    return {
        "report_date": d.isoformat(),
        "total_articles": all_total,
        "overall_avg_signal_score": overall_avg,
        "overall_noise_ratio": round(all_noise / max(1, all_total), 2),
        "topics": topic_metrics,
        "top_signal_sources": top_sources,
    }
