"""Morning Intelligence Briefing narrative generation."""

from app.narrative.service import generate_daily_narrative, load_narrative_for_api

__all__ = ["generate_daily_narrative", "load_narrative_for_api"]
