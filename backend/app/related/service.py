"""Related articles service (Phase 31). Orchestrates matching + repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.related.matching import extract_query_signature, score_candidate
from app.related.repository import fetch_candidate_articles

_MIN_SCORE = 0.05  # require at least a faint title overlap or a shared entity
_CANDIDATE_POOL_DAYS = 7
_CANDIDATE_POOL_LIMIT = 500


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _published_at_key(row: dict[str, Any]):
    ts = row.get("published_at")
    if ts is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _to_related_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": row["title"],
        "summary": row.get("summary") or "",
        "why_it_matters": row.get("why_it_matters") or "",
        "source": row.get("source") or "",
        "url": row.get("url") or "",
        "image_url": row.get("image_url"),
        "published_at": row["published_at"].isoformat() if row.get("published_at") else None,
        "topic": row.get("topic_name"),
    }


def get_related_articles(
    title: str,
    topic: Optional[str],
    exclude_url: Optional[str],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Rank candidate articles (last 7 days, all active topics) against `title`
    by shared entities + title token overlap. Returns [] when nothing clears
    the relevance floor — no unrelated filler.
    """
    query_entities, query_tokens = extract_query_signature(title)

    candidates = fetch_candidate_articles(
        exclude_url=exclude_url,
        days=_CANDIDATE_POOL_DAYS,
        pool_limit=_CANDIDATE_POOL_LIMIT,
    )

    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in candidates:
        score = score_candidate(
            query_entities,
            query_tokens,
            topic,
            candidate["title"],
            candidate.get("topic_name"),
        )
        if score >= _MIN_SCORE:
            scored.append((score, candidate))

    scored.sort(key=lambda pair: (-pair[0], -_published_at_key(pair[1]).timestamp()))

    _log(
        "related_articles_computed",
        candidates=len(candidates),
        matched=len(scored),
        returned=min(limit, len(scored)),
    )

    return [_to_related_item(row) for _, row in scored[:limit]]
