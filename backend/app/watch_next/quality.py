"""Watch Next quality gate (Phase 17.5)."""

from __future__ import annotations

from app.watch_next.generator import _is_generic, _similar


def run_watch_next_quality_gate(items: list[dict]) -> dict:
    """
    Return {passed, errors, warnings}.
    Failure does not block pipeline — stored as status=failed.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if len(items) < 2:
        errors.append("item_count_below_minimum")
    if len(items) > 6:
        warnings.append("item_count_above_recommended_max")

    if items and all(not item.get("supporting_article_ids") for item in items):
        errors.append("no_supporting_articles")

    generic_count = sum(1 for item in items if _is_generic(item.get("text", "")))
    if items and generic_count == len(items):
        errors.append("all_items_generic")

    concrete_count = sum(
        1
        for item in items
        if (item.get("topics") or item.get("impact_types"))
    )
    if items and concrete_count == 0:
        errors.append("no_concrete_topic_or_impact")

    seen: list[str] = []
    for item in items:
        text = item.get("text") or ""
        if any(_similar(text, prior) for prior in seen):
            warnings.append("duplicate_or_similar_items")
            break
        seen.append(text)

    passed = len(errors) == 0
    return {"passed": passed, "errors": errors, "warnings": warnings}
