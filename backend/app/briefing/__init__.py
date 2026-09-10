"""
WhatsNews Narrative Briefing Layer (Phase 26).

Transforms Phase 25 event clusters into structured narrative intelligence:

  Event → Narrative Block
    {headline, what_happened, why_it_matters, what_changed, watch_next}

Public API:
  get_daily_briefing(topic, report_date) → dict
"""

from app.briefing.service import get_daily_briefing

__all__ = ["get_daily_briefing"]
