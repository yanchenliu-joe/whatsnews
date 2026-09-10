"""Pure feed/topic health scoring helpers shared by the feed diagnostics and recommendation routes."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def _feed_health_status(row: dict) -> str:
    """Classify a feed row as 'healthy', 'warning', or 'failed'."""
    if not row["is_active"] or (row.get("consecutive_failures") or 0) >= 5:
        return "failed"
    if (row.get("consecutive_failures") or 0) > 0:
        return "warning"
    return "healthy"


def _feed_reliability_score(row: dict) -> int:
    total = (row.get("failure_count") or 0) + (row.get("success_count") or 0)
    if total == 0:
        return 100  # new feed, no history yet
    return round(100 * (row.get("success_count") or 0) / total)


def _compute_feed_quality_score(row: dict) -> dict:
    """
    Compute a 0–100 quality score for a feed based on DB reliability columns.

    Components:
      success_rate_score  (0–50): historical success ratio
      reliability_score   (0–30): consecutive_failures + active status
      freshness_score     (0–20): time since last successful fetch

    New feeds (no history yet) receive a neutral starting score of 70.
    """
    success_count = row.get("success_count") or 0
    failure_count = row.get("failure_count") or 0
    consecutive_failures = row.get("consecutive_failures") or 0
    is_active = row.get("is_active", True)
    last_success_at = row.get("last_success_at")

    total_fetches = success_count + failure_count

    if total_fetches == 0:
        return {
            "success_rate_score": 35,
            "reliability_score": 25,
            "freshness_score": 10,
            "total": 70,
            "classification": "medium_risk",
            "note": "new_feed_no_history",
        }

    # Success rate component (0–50)
    success_rate_score = round(50 * success_count / total_fetches)

    # Reliability component (0–30)
    if not is_active:
        reliability_component = 0
    elif consecutive_failures == 0:
        reliability_component = 30
    elif consecutive_failures <= 2:
        reliability_component = 15
    elif consecutive_failures <= 4:
        reliability_component = 5
    else:
        reliability_component = 0

    # Freshness component (0–20) — how recently the feed returned articles
    if last_success_at is None:
        freshness_score = 0
    else:
        now = datetime.now(tz=ZoneInfo("UTC"))
        if last_success_at.tzinfo is None:
            last_success_at = last_success_at.replace(tzinfo=ZoneInfo("UTC"))
        age_hours = (now - last_success_at).total_seconds() / 3600
        if age_hours < 24:
            freshness_score = 20
        elif age_hours < 48:
            freshness_score = 15
        elif age_hours < 168:
            freshness_score = 10
        elif age_hours < 720:
            freshness_score = 5
        else:
            freshness_score = 0

    total = success_rate_score + reliability_component + freshness_score

    if total >= 80:
        classification = "stable"
    elif total >= 50:
        classification = "medium_risk"
    else:
        classification = "candidate_for_removal"

    return {
        "success_rate_score": success_rate_score,
        "reliability_score": reliability_component,
        "freshness_score": freshness_score,
        "total": total,
        "classification": classification,
    }


def _compute_topic_health_score(topic_data: dict, recent_article_count: int) -> dict:
    """
    Compute a 0–100 health score for a topic based on feed health and article volume.

    Components:
      feed_success_pct_score    (0–60): fraction of feeds classified as healthy
      article_volume_score      (0–20): recent (7-day) article activity
      failure_isolation_score   (0–20): whether enough feeds remain viable
    """
    total = topic_data.get("total", 0)
    healthy = topic_data.get("healthy", 0)

    # Feed success pct (0–60)
    feed_success_pct_score = round(60 * healthy / total) if total else 0

    # Article volume score (0–20)
    if recent_article_count >= 5:
        article_volume_score = 20
    elif recent_article_count >= 3:
        article_volume_score = 15
    elif recent_article_count >= 1:
        article_volume_score = 10
    else:
        article_volume_score = 0

    # Failure isolation (0–20): full score if ≥1/3 of feeds are healthy
    if total == 0:
        failure_isolation_score = 0
    elif healthy >= max(1, total // 3):
        failure_isolation_score = 20
    elif healthy > 0:
        failure_isolation_score = 10
    else:
        failure_isolation_score = 0

    total_score = feed_success_pct_score + article_volume_score + failure_isolation_score

    if total_score >= 80:
        classification = "healthy"
    elif total_score >= 50:
        classification = "degraded"
    else:
        classification = "critical"

    return {
        "feed_success_pct_score": feed_success_pct_score,
        "article_volume_score": article_volume_score,
        "failure_isolation_score": failure_isolation_score,
        "total": total_score,
        "classification": classification,
    }
