"""Pipeline-facing editorial perspective metrics (Phase 17.3)."""

from __future__ import annotations

PERSPECTIVE_METRIC_DEFAULTS: dict = {
    "status": "skipped",
    "perspective_status": "missing",
    "perspective_confidence": None,
    "perspective_theme_count": 0,
    "perspective_supporting_article_count": 0,
    "perspective_generation_seconds": 0.0,
    "perspective_id": None,
    "version": None,
}


def empty_perspective_stats(*, status: str = "skipped") -> dict:
    stats = dict(PERSPECTIVE_METRIC_DEFAULTS)
    stats["status"] = status
    return stats


def normalize_perspective_stats(raw: dict | None) -> dict:
    stats = empty_perspective_stats()
    if not raw:
        return stats

    for key in PERSPECTIVE_METRIC_DEFAULTS:
        if key in raw and raw[key] is not None:
            stats[key] = raw[key]

    if raw.get("error"):
        stats["error"] = raw["error"]
    if raw.get("reason"):
        stats["reason"] = raw["reason"]
    if raw.get("quality_gate"):
        stats["quality_gate"] = raw["quality_gate"]

    stats["perspective_theme_count"] = int(stats.get("perspective_theme_count") or 0)
    stats["perspective_supporting_article_count"] = int(
        stats.get("perspective_supporting_article_count") or 0
    )
    stats["perspective_generation_seconds"] = round(
        float(stats.get("perspective_generation_seconds") or 0.0), 2
    )
    return stats
