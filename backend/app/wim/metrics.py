"""Pipeline-facing WIM generation metrics (Phase 16.1 / 17.2)."""

from __future__ import annotations

GENERATION_METRIC_DEFAULTS: dict = {
    "status": "completed",
    "topics_processed": 0,
    "articles_generated": 0,
    "articles_checked": 0,
    "wim_requests": 0,
    "wim_articles_generated": 0,
    "average_articles_per_request": 0.0,
    "wim_cache_hits": 0,
    "wim_fallback_count": 0,
    "ai_refine_attempted": 0,
    "ai_refine_success": 0,
    "ai_refine_fallback": 0,
    "batch_articles": 0,
    "wim_quality_pass_count": 0,
    "wim_quality_fallback_count": 0,
    "generic_phrase_block_count": 0,
    "impact_type_distribution": {},
}


def empty_generation_stats(*, status: str = "completed") -> dict:
    stats = dict(GENERATION_METRIC_DEFAULTS)
    stats["status"] = status
    return stats


def _merge_impact_distribution(target: dict, incoming: dict | None) -> None:
    if not incoming:
        return
    for impact, count in incoming.items():
        target[impact] = target.get(impact, 0) + int(count or 0)


def normalize_generation_stats(raw: dict | None) -> dict:
    """
    Ensure /admin/run-pipeline always returns numeric WIM metric fields
    (never null / missing) on stats.generation.
    """
    stats = empty_generation_stats()
    if not raw:
        return stats

    for key in GENERATION_METRIC_DEFAULTS:
        if key in raw and raw[key] is not None:
            stats[key] = raw[key]

    if raw.get("error"):
        stats["error"] = raw["error"]
        stats["status"] = raw.get("status") or "failed"
    elif raw.get("status"):
        stats["status"] = raw["status"]

    wim_requests = int(stats.get("wim_requests") or 0)
    batch_articles = int(stats.get("batch_articles") or 0)
    if wim_requests > 0:
        stats["average_articles_per_request"] = round(batch_articles / wim_requests, 2)
    else:
        stats["average_articles_per_request"] = float(
            stats.get("average_articles_per_request") or 0.0
        )

    impact = stats.get("impact_type_distribution") or {}
    stats["impact_type_distribution"] = dict(impact) if isinstance(impact, dict) else {}

    return stats


def merge_generation_totals(totals: dict, result: dict) -> None:
    """Merge per-topic generation stats into pipeline totals."""
    totals["topics_processed"] += 1
    totals["articles_checked"] += result.get("articles_checked", 0)
    totals["articles_generated"] += result.get("articles_generated", 0)
    totals["wim_requests"] += result.get("wim_requests", 0)
    totals["wim_articles_generated"] += result.get("wim_articles_generated", 0)
    totals["wim_cache_hits"] += result.get("wim_cache_hits", 0)
    totals["wim_fallback_count"] += result.get("wim_fallback_count", 0)
    totals["batch_articles"] += result.get("batch_articles", 0)
    totals["ai_refine_attempted"] += result.get("ai_refine_attempted", 0)
    totals["ai_refine_success"] += result.get("ai_refine_success", 0)
    totals["ai_refine_fallback"] += result.get("ai_refine_fallback", 0)
    totals["wim_quality_pass_count"] += result.get("wim_quality_pass_count", 0)
    totals["wim_quality_fallback_count"] += result.get(
        "wim_quality_fallback_count", 0
    )
    totals["generic_phrase_block_count"] += result.get(
        "generic_phrase_block_count", 0
    )
    _merge_impact_distribution(
        totals["impact_type_distribution"],
        result.get("impact_type_distribution"),
    )
