"""Pipeline-facing editorial engine metrics (Phase 17.1)."""

from __future__ import annotations

EDITORIAL_METRIC_DEFAULTS: dict = {
    "status": "completed",
    "articles_processed": 0,
    "average_importance": 0.0,
    "impact_distribution": {},
    "top_editorial_tags": [],
    "metadata_persisted": 0,
}

TOP_TAGS_LIMIT = 10


def empty_editorial_stats(*, status: str = "completed") -> dict:
    stats = dict(EDITORIAL_METRIC_DEFAULTS)
    stats["status"] = status
    return stats


def normalize_editorial_stats(raw: dict | None) -> dict:
    """Ensure pipeline response always includes numeric editorial_engine fields."""
    stats = empty_editorial_stats()
    if not raw:
        return stats

    for key in EDITORIAL_METRIC_DEFAULTS:
        if key in raw and raw[key] is not None:
            stats[key] = raw[key]

    if raw.get("error"):
        stats["error"] = raw["error"]
        stats["status"] = raw.get("status") or "failed"
    elif raw.get("status"):
        stats["status"] = raw["status"]

    stats["articles_processed"] = int(stats.get("articles_processed") or 0)
    stats["average_importance"] = round(float(stats.get("average_importance") or 0.0), 1)
    stats["metadata_persisted"] = int(stats.get("metadata_persisted") or 0)

    impact = stats.get("impact_distribution") or {}
    stats["impact_distribution"] = dict(impact) if isinstance(impact, dict) else {}

    tags = stats.get("top_editorial_tags") or []
    stats["top_editorial_tags"] = list(tags) if isinstance(tags, list) else []

    return stats
