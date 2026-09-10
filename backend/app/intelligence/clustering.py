"""
Event clustering engine (Phase 25).

Groups articles that cover the same real-world event using:
  - Title token Jaccard similarity (threshold ≥ 0.35)
  - 72-hour publication window
  - Signal-score-first ordering (highest-signal article becomes event lead)

Output is a list of Event dicts, each containing the merged view of 1–N articles.
No ML or external APIs required.
"""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo

_CLUSTER_THRESHOLD = 0.35     # Jaccard similarity to join an existing cluster
_TIME_WINDOW_HOURS = 72       # maximum hours between articles in a cluster

# Signal score bonus for cluster size (rewards multi-source coverage)
_SIZE_BONUS: dict[int, int] = {1: 0, 2: 5, 3: 10, 4: 12, 5: 15}
_MAX_BONUS = 15


def _tokens(title: str) -> frozenset[str]:
    return frozenset(re.sub(r"[^\w\s]", "", (title or "").lower()).split())


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _safe_ts(ts):
    if ts is None:
        return None
    if hasattr(ts, "tzinfo") and ts.tzinfo is None:
        return ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts


def _hours_apart(ts_a, ts_b) -> float:
    a, b = _safe_ts(ts_a), _safe_ts(ts_b)
    if a is None or b is None:
        return 0.0
    return abs((a - b).total_seconds()) / 3600


def _article_row(article: dict) -> dict:
    pub = article.get("published_at")
    return {
        "id": article.get("id"),
        "title": article.get("title"),
        "url": article.get("url"),
        "source": article.get("source"),
        "published_at": pub.isoformat() if pub else None,
        "signal_score": article.get("signal_score", 0),
        "signal_tier": article.get("signal_tier", "noise"),
        "why_it_matters": article.get("why_it_matters"),
        "summary": article.get("summary"),
        "body_text": article.get("body_text"),
        "editorial_metadata": article.get("editorial_metadata"),
        "image_url": article.get("image_url"),
    }


def cluster_articles(articles: list[dict]) -> list[dict]:
    """
    Cluster articles into events by title similarity within a 72-hour window.

    Returns a list of event dicts sorted by event signal_score DESC.
    Each event has:
      event_title, signal_score, signal_tier, summary, sources_count,
      sources, supporting_article_count, top_articles (up to 3)
    """
    if not articles:
        return []

    # Lead of each cluster = highest signal article, so sort descending first
    sorted_articles = sorted(
        articles,
        key=lambda a: a.get("signal_score", 0),
        reverse=True,
    )

    # Each cluster: {_tokens, _lead_pub, articles[]}
    clusters: list[dict] = []

    for article in sorted_articles:
        tok = _tokens(article.get("title", ""))
        pub = article.get("published_at")
        placed = False

        for cl in clusters:
            # Time window guard
            if _hours_apart(pub, cl["_lead_pub"]) > _TIME_WINDOW_HOURS:
                continue
            # Similarity check against cluster lead tokens
            if _jaccard(tok, cl["_lead_tokens"]) >= _CLUSTER_THRESHOLD:
                cl["articles"].append(article)
                placed = True
                break

        if not placed:
            clusters.append({
                "_lead_tokens": tok,
                "_lead_pub": pub,
                "articles": [article],
            })

    # Build output
    result: list[dict] = []
    for cl in clusters:
        members = cl["articles"]
        lead = members[0]  # highest signal (due to pre-sort)
        size = len(members)
        bonus = _SIZE_BONUS.get(size, _MAX_BONUS)
        final_score = min(100, lead.get("signal_score", 0) + bonus)
        sources = list({a.get("source") for a in members if a.get("source")})

        result.append({
            "event_title": lead.get("title") or "Untitled Event",
            "signal_score": final_score,
            "signal_tier": (
                "high"          if final_score >= 70
                else "informational" if final_score >= 40
                else "noise"
            ),
            "summary": lead.get("why_it_matters") or lead.get("summary") or "",
            "sources_count": len(sources),
            "sources": sorted(sources)[:5],
            "supporting_article_count": size,
            "top_articles": [_article_row(a) for a in members[:3]],
        })

    result.sort(key=lambda e: e["signal_score"], reverse=True)
    return result
