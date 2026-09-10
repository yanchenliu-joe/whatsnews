"""
Editorial importance scoring (Phase 17.1).

Deterministic 0–100 score for each selected article.  No AI, no embeddings.

Formula (sum capped at 100)
---------------------------
1. Signal tier (0–30)
   Uses assembly.compute_importance_score tier (0–3):
     tier 3 → 30, tier 2 → 20, tier 1 → 10, tier 0 → 0

2. Recency (0–20)
   Hours since effective_date (published_at, else fetched_at):
     ≤ 6 h  → 20
     ≤ 24 h → 15
     ≤ 48 h → 10
     ≤ 96 h →  5
     else   →  0

3. Source credibility (0–15)
   SOURCE_CREDIBILITY_TIER lookup on articles.source:
     tier 3 → 15, tier 2 → 10, tier 1 → 5, unknown → 3

4. Topic relevance (0–10)
   passes_relevance_filter(title, summary, topic) → 10, else 3

5. Cross-topic bridge match (0–10)
   Any bridge keyword in title+summary → 10, else 0

6. Impact signal density (0–15)
   min(15, distinct_impact_types × 5) — rewards multi-dimensional stories
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.assembly import compute_importance_score, passes_relevance_filter
from app.editorial.bridges import matches_any_bridge_keyword

# Source name → credibility tier (1–3).  Partial name match supported.
SOURCE_CREDIBILITY_TIER: dict[str, int] = {
    "bbc": 3,
    "reuters": 3,
    "financial times": 3,
    "ft ": 3,
    "wall street journal": 3,
    "wsj": 3,
    "ap news": 3,
    "associated press": 3,
    "nature": 3,
    "science": 3,
    "arstechnica": 2,
    "techcrunch": 2,
    "bloomberg": 2,
    "cnbc": 2,
    "the verge": 2,
    "wired": 2,
    "stat news": 2,
    "politico": 2,
    "defense news": 2,
    "cybersecurity": 2,
}

_TIER_POINTS = {3: 30, 2: 20, 1: 10, 0: 0}
_CREDIBILITY_POINTS = {3: 15, 2: 10, 1: 5}


def _source_credibility_tier(source: str) -> int:
    normalized = (source or "").lower().strip()
    if not normalized:
        return 0
    for key, tier in SOURCE_CREDIBILITY_TIER.items():
        if key in normalized:
            return tier
    return 1


def _recency_points(effective_date: datetime | None) -> int:
    if effective_date is None:
        return 0
    now = datetime.now(tz=ZoneInfo("UTC"))
    if effective_date.tzinfo is None:
        effective_date = effective_date.replace(tzinfo=ZoneInfo("UTC"))
    hours = (now - effective_date).total_seconds() / 3600
    if hours <= 6:
        return 20
    if hours <= 24:
        return 15
    if hours <= 48:
        return 10
    if hours <= 96:
        return 5
    return 0


def compute_editorial_importance_score(
    *,
    title: str,
    summary: str,
    source: str,
    topic_name: str,
    effective_date: datetime | None,
    impact_type_count: int,
) -> tuple[int, dict[str, int]]:
    """
    Return (score 0–100, breakdown dict).
    """
    tier = compute_importance_score(title, summary, topic_name)
    signal = _TIER_POINTS.get(tier, 0)
    recency = _recency_points(effective_date)
    cred_tier = _source_credibility_tier(source)
    credibility = _CREDIBILITY_POINTS.get(cred_tier, 3)
    relevance = 10 if passes_relevance_filter(title, summary, topic_name) else 3
    cross_topic = 10 if matches_any_bridge_keyword(title, summary) else 0
    impact_density = min(15, max(0, impact_type_count) * 5)

    breakdown = {
        "signal_tier": signal,
        "recency": recency,
        "source_credibility": credibility,
        "topic_relevance": relevance,
        "cross_topic": cross_topic,
        "impact_density": impact_density,
    }
    score = min(100, sum(breakdown.values()))
    return score, breakdown
