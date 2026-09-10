"""Persist why_it_matters for report articles."""

from __future__ import annotations

import json

from app.editorial.service import get_article_profile
from app.wim.batch import PendingWimArticle, refine_topic_batch_with_ai
from app.wim.editorial_wim import generate_editorial_why_it_matters


def fill_missing_why_it_matters(cur, articles: list, topic_name: str) -> dict:
    """
    Generate and persist why_it_matters for articles missing it.

    Phase 17.2: uses editorial metadata, structured batch JSON, and a
    quality gate with impact-aware rule fallback.

    Does NOT commit — caller is responsible for conn.commit().
    """
    checked = 0
    generated = 0
    ai_attempted = 0
    ai_success = 0
    ai_fallback = 0
    wim_requests = 0
    wim_articles_generated = 0
    wim_cache_hits = 0
    wim_fallback_count = 0
    batch_articles = 0
    wim_quality_pass_count = 0
    wim_quality_fallback_count = 0
    generic_phrase_block_count = 0
    impact_type_distribution: dict[str, int] = {}

    pending_rows: list[dict] = []
    for row in articles:
        checked += 1
        if row.get("why_it_matters"):
            continue
        pending_rows.append(row)

    if not pending_rows:
        return _result_dict(
            checked=checked,
            generated=generated,
            ai_attempted=ai_attempted,
            ai_success=ai_success,
            ai_fallback=ai_fallback,
            wim_requests=wim_requests,
            wim_articles_generated=wim_articles_generated,
            wim_cache_hits=wim_cache_hits,
            wim_fallback_count=wim_fallback_count,
            batch_articles=batch_articles,
            wim_quality_pass_count=wim_quality_pass_count,
            wim_quality_fallback_count=wim_quality_fallback_count,
            generic_phrase_block_count=generic_phrase_block_count,
            impact_type_distribution=impact_type_distribution,
        )

    pending_articles: list[PendingWimArticle] = []
    for row in pending_rows:
        editorial_metadata = _resolve_editorial_metadata(row)
        draft = generate_editorial_why_it_matters(
            title=row["title"],
            summary=row.get("summary") or "",
            topic=topic_name,
            source=row.get("source") or "",
            editorial_metadata=editorial_metadata,
        )
        pending_articles.append(
            PendingWimArticle(
                article_id=row["id"],
                title=row["title"],
                summary=row.get("summary") or "",
                source=row.get("source") or "",
                base_text=draft["why_it_matters"],
                editorial_metadata=editorial_metadata,
            )
        )

    batch_results, metrics = refine_topic_batch_with_ai(topic_name, pending_articles)
    wim_requests += metrics.wim_requests
    batch_articles += metrics.batch_articles
    wim_quality_pass_count += metrics.wim_quality_pass_count
    wim_quality_fallback_count += metrics.wim_quality_fallback_count
    generic_phrase_block_count += metrics.generic_phrase_block_count
    for impact, count in metrics.impact_type_distribution.items():
        impact_type_distribution[impact] = (
            impact_type_distribution.get(impact, 0) + count
        )

    for row in pending_rows:
        outcome = batch_results.get(row["id"])
        if outcome is None:
            continue

        if outcome.status == "cache_hit":
            wim_cache_hits += 1
        elif outcome.status in ("ai_fallback", "quality_fallback"):
            ai_fallback += 1
            wim_fallback_count += 1
        elif outcome.status == "ai_success":
            ai_success += 1

        if outcome.status in ("ai_success", "ai_fallback", "quality_fallback"):
            ai_attempted += 1

        cur.execute(
            "UPDATE articles SET why_it_matters = %s WHERE id = %s",
            (outcome.text, row["id"]),
        )
        row["why_it_matters"] = outcome.text
        _persist_wim_metadata(cur, row["id"], row, outcome)
        generated += 1
        wim_articles_generated += 1

    return _result_dict(
        checked=checked,
        generated=generated,
        ai_attempted=ai_attempted,
        ai_success=ai_success,
        ai_fallback=ai_fallback,
        wim_requests=wim_requests,
        wim_articles_generated=wim_articles_generated,
        wim_cache_hits=wim_cache_hits,
        wim_fallback_count=wim_fallback_count,
        batch_articles=batch_articles,
        wim_quality_pass_count=wim_quality_pass_count,
        wim_quality_fallback_count=wim_quality_fallback_count,
        generic_phrase_block_count=generic_phrase_block_count,
        impact_type_distribution=impact_type_distribution,
    )


def _resolve_editorial_metadata(row: dict) -> dict:
    db_meta = row.get("editorial_metadata")
    if isinstance(db_meta, str):
        try:
            db_meta = json.loads(db_meta)
        except json.JSONDecodeError:
            db_meta = None
    if isinstance(db_meta, dict) and db_meta:
        return db_meta
    profile = get_article_profile(row["id"])
    if profile:
        return profile
    return {}


def _persist_wim_metadata(cur, article_id: int, row: dict, outcome) -> None:
    existing = row.get("editorial_metadata")
    if not isinstance(existing, dict):
        existing = _resolve_editorial_metadata(row)

    wim_block = dict(outcome.wim_meta or {})
    quality_flags = list(outcome.quality_flags or [])
    if quality_flags:
        wim_block["quality_flags"] = quality_flags

    merged = dict(existing)
    merged["wim"] = wim_block

    try:
        cur.execute(
            """
            UPDATE articles
            SET editorial_metadata = %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(merged), article_id),
        )
        row["editorial_metadata"] = merged
    except Exception:
        pass


def _result_dict(
    *,
    checked: int,
    generated: int,
    ai_attempted: int,
    ai_success: int,
    ai_fallback: int,
    wim_requests: int,
    wim_articles_generated: int,
    wim_cache_hits: int,
    wim_fallback_count: int,
    batch_articles: int,
    wim_quality_pass_count: int,
    wim_quality_fallback_count: int,
    generic_phrase_block_count: int,
    impact_type_distribution: dict[str, int],
) -> dict:
    average_articles_per_request = (
        round(batch_articles / wim_requests, 2) if wim_requests else 0.0
    )
    return {
        "articles_checked": checked,
        "articles_generated": generated,
        "ai_refine_attempted": ai_attempted,
        "ai_refine_success": ai_success,
        "ai_refine_fallback": ai_fallback,
        "wim_requests": wim_requests,
        "wim_articles_generated": wim_articles_generated,
        "average_articles_per_request": average_articles_per_request,
        "wim_cache_hits": wim_cache_hits,
        "wim_fallback_count": wim_fallback_count,
        "batch_articles": batch_articles,
        "wim_quality_pass_count": wim_quality_pass_count,
        "wim_quality_fallback_count": wim_quality_fallback_count,
        "generic_phrase_block_count": generic_phrase_block_count,
        "impact_type_distribution": impact_type_distribution,
    }
