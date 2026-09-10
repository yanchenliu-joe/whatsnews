"""
WhatsNews Intelligence Layer (Phase 25).

Transforms raw assembled articles into a signal-scored, event-clustered
daily intelligence briefing.

Article → Signal → Event

Public API:
  get_daily_intelligence(topic, report_date) → dict
  get_signal_metrics_for_all_topics()        → dict
"""

from app.intelligence.service import (
    get_daily_intelligence,
    get_signal_metrics_for_all_topics,
)

__all__ = [
    "get_daily_intelligence",
    "get_signal_metrics_for_all_topics",
]
