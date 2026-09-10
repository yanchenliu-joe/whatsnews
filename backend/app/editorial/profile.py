"""Editorial profile assembly (Phase 17.1)."""

from __future__ import annotations

from datetime import datetime

from app.editorial.bridges import detect_cross_topic_candidates
from app.editorial.impact import detect_impact_types
from app.editorial.ranking import compute_editorial_importance_score
from app.editorial.tags import extract_editorial_tags


def compute_confidence(
    importance_score: int,
    impact_types: list[str],
    editorial_tags: list[str],
) -> str:
    """
    Rule-based confidence in the editorial profile (not factual certainty).

    high   — strong signal: score ≥ 65 OR (≥ 2 impact types AND ≥ 2 tags)
    medium — moderate signal: score ≥ 40 OR ≥ 1 impact type
    low    — thin signal otherwise
    """
    if importance_score >= 65 or (
        len(impact_types) >= 2 and len(editorial_tags) >= 2
    ):
        return "high"
    if importance_score >= 40 or len(impact_types) >= 1:
        return "medium"
    return "low"


def build_editorial_profile(
    *,
    title: str,
    summary: str,
    source: str,
    topic_name: str,
    effective_date: datetime | None,
) -> dict:
    """
    Build a lightweight editorial profile for one selected article.
    """
    impact_types = detect_impact_types(title, summary)
    editorial_tags = extract_editorial_tags(title, summary)
    cross_topic_candidates = detect_cross_topic_candidates(title, summary)

    importance_score, score_breakdown = compute_editorial_importance_score(
        title=title,
        summary=summary,
        source=source,
        topic_name=topic_name,
        effective_date=effective_date,
        impact_type_count=len(impact_types),
    )
    confidence = compute_confidence(
        importance_score, impact_types, editorial_tags
    )

    return {
        "importance_score": importance_score,
        "impact_types": impact_types,
        "confidence": confidence,
        "cross_topic_candidates": cross_topic_candidates,
        "editorial_tags": editorial_tags,
        "score_breakdown": score_breakdown,
        "topic": topic_name,
    }
