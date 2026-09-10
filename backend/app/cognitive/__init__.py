"""
WhatsNews Cognitive Intelligence Layer (Phase 27).

Transforms Phase 26 narrative blocks into cognitively-enriched briefing items:

  Narrative Block → Cognitive Block
    {so_what, impact_level, risk_level, who_is_affected, action_implication, confidence}

Public API:
  get_daily_cognitive(topic, report_date) → dict
"""

from app.cognitive.service import get_daily_cognitive

__all__ = ["get_daily_cognitive"]
