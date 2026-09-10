"""
Product analytics — the /events tracking allow-list and insert helper.

Public API:
  VALID_EVENT_NAMES: frozenset[str]
  _record_event(event_name, article_id=None, topic_name=None, metadata_text=None) -> None
"""

from app.analytics.events import VALID_EVENT_NAMES, _record_event

__all__ = ["VALID_EVENT_NAMES", "_record_event"]
