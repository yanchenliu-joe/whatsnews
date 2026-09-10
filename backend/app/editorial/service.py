"""
Editorial Engine service (Phase 17.1).

Runs after assembly, before WIM generation.  Produces structured editorial
metadata for each selected article and aggregates pipeline diagnostics.
"""

from __future__ import annotations

from collections import Counter

from app.database import get_connection
from app.editorial.config import editorial_engine_enabled
from app.editorial.metrics import (
    TOP_TAGS_LIMIT,
    empty_editorial_stats,
    normalize_editorial_stats,
)
from app.editorial.persist import EditorialMetadataColumnMissing, persist_article_profiles
from app.editorial.profile import build_editorial_profile

# In-memory registry for downstream pipeline stages (WIM, narrative — future phases).
_ARTICLE_PROFILES: dict[int, dict] = {}


def get_article_profile(article_id: int) -> dict | None:
    """Return editorial profile for an article from the latest engine run."""
    return _ARTICLE_PROFILES.get(article_id)


def clear_profile_registry() -> None:
    _ARTICLE_PROFILES.clear()


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _load_todays_selected_articles(cur) -> list[dict]:
    cur.execute(
        """
        SELECT
            a.id,
            a.title,
            COALESCE(a.summary, '') AS summary,
            COALESCE(a.source, '') AS source,
            COALESCE(a.published_at, a.fetched_at) AS effective_date,
            t.name AS topic_name
        FROM articles a
        JOIN daily_reports dr ON dr.id = a.report_id
        JOIN topics t ON t.id = dr.topic_id
        WHERE dr.report_date = CURRENT_DATE
        ORDER BY t.sort_order ASC, t.name ASC, a.id ASC
        """
    )
    return [dict(row) for row in cur.fetchall()]


def _aggregate_metrics(profiles: dict[int, dict]) -> dict:
    if not profiles:
        return empty_editorial_stats()

    scores = [p["importance_score"] for p in profiles.values()]
    impact_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()

    for profile in profiles.values():
        for impact in profile.get("impact_types") or []:
            impact_counter[impact] += 1
        for tag in profile.get("editorial_tags") or []:
            tag_counter[tag] += 1

    top_tags = [
        {"tag": tag, "count": count}
        for tag, count in tag_counter.most_common(TOP_TAGS_LIMIT)
    ]

    return {
        "status": "completed",
        "articles_processed": len(profiles),
        "average_importance": round(sum(scores) / len(scores), 1),
        "impact_distribution": dict(sorted(impact_counter.items())),
        "top_editorial_tags": top_tags,
        "metadata_persisted": 0,
    }


def run_editorial_engine() -> dict:
    """
    Analyze today's selected articles and produce editorial metadata.

    Returns stats for stats.editorial_engine in the pipeline response.
    """
    if not editorial_engine_enabled():
        stats = empty_editorial_stats(status="skipped")
        stats["reason"] = "editorial_engine_disabled"
        return normalize_editorial_stats(stats)

    _log("editorial_engine_started")
    clear_profile_registry()

    try:
        conn = get_connection()
    except ValueError as exc:
        stats = empty_editorial_stats(status="failed")
        stats["error"] = str(exc)[:500]
        _log("editorial_engine_failed", error=stats["error"])
        return normalize_editorial_stats(stats)

    cur = conn.cursor()
    profiles: dict[int, dict] = {}

    try:
        rows = _load_todays_selected_articles(cur)
        for row in rows:
            profile = build_editorial_profile(
                title=row["title"],
                summary=row["summary"],
                source=row["source"],
                topic_name=row["topic_name"],
                effective_date=row.get("effective_date"),
            )
            profiles[row["id"]] = profile
            _ARTICLE_PROFILES[row["id"]] = profile

        stats = _aggregate_metrics(profiles)

        try:
            persisted = persist_article_profiles(cur, profiles)
            conn.commit()
            stats["metadata_persisted"] = persisted
        except EditorialMetadataColumnMissing:
            conn.rollback()
            stats["metadata_persisted"] = 0
            stats["persist_warning"] = (
                "articles.editorial_metadata column missing — run migration 0009"
            )
            _log(
                "editorial_metadata_persist_skipped",
                reason="column_missing",
                articles=len(profiles),
            )

        _log(
            "editorial_engine_completed",
            articles=stats["articles_processed"],
            average_importance=stats["average_importance"],
            persisted=stats["metadata_persisted"],
        )
        return normalize_editorial_stats(stats)

    except Exception as exc:
        conn.rollback()
        stats = empty_editorial_stats(status="failed")
        stats["error"] = str(exc)[:500]
        _log("editorial_engine_failed", error=stats["error"])
        return normalize_editorial_stats(stats)
    finally:
        cur.close()
        conn.close()
