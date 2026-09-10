"""Pipeline-facing Watch Next metrics (Phase 17.5)."""

from __future__ import annotations

WATCH_NEXT_METRIC_DEFAULTS: dict = {
    "status": "skipped",
    "watch_next_status": "missing",
    "watch_next_item_count": 0,
    "watch_next_confidence_distribution": {},
    "watch_next_generation_seconds": 0.0,
    "watch_next_id": None,
    "version": None,
}


def empty_watch_next_stats(*, status: str = "skipped") -> dict:
    stats = dict(WATCH_NEXT_METRIC_DEFAULTS)
    stats["status"] = status
    return stats


def normalize_watch_next_stats(raw: dict | None) -> dict:
    stats = empty_watch_next_stats()
    if not raw:
        return stats

    for key in WATCH_NEXT_METRIC_DEFAULTS:
        if key in raw and raw[key] is not None:
            stats[key] = raw[key]

    if raw.get("error"):
        stats["error"] = raw["error"]
    if raw.get("reason"):
        stats["reason"] = raw["reason"]
    if raw.get("quality_gate"):
        stats["quality_gate"] = raw["quality_gate"]

    stats["watch_next_item_count"] = int(stats.get("watch_next_item_count") or 0)
    stats["watch_next_generation_seconds"] = round(
        float(stats.get("watch_next_generation_seconds") or 0.0), 2
    )
    dist = stats.get("watch_next_confidence_distribution") or {}
    stats["watch_next_confidence_distribution"] = dict(dist) if isinstance(dist, dict) else {}
    return stats
