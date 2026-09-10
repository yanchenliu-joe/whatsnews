"""
Related articles (Phase 31).

Given an article's title, ranks candidate articles from the last 7 days
(across all topics) by shared named entities + title token overlap. No
embeddings, no new tables — read-time only, same pattern as the
intelligence/briefing/cognitive/feed layers (Phase 25-28).

Public API:
  get_related_articles(title, topic, exclude_url, limit) -> list[dict]
"""

from app.related.service import get_related_articles

__all__ = ["get_related_articles"]
