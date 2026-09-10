"""
Cognitive briefing routes (Phase 27).

Public:
  GET /daily-cognitive?topic=AI[&date=YYYY-MM-DD][&emerging=true]
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import HTTPException, Query

from app.cognitive.service import get_daily_cognitive
from app.log_utils import _log


def register_cognitive_routes(app):
    @app.get("/daily-cognitive")
    def daily_cognitive(
        topic: str = Query(..., description="Topic name"),
        date: date_type | None = Query(
            None, description="Report date YYYY-MM-DD (defaults to today)"
        ),
        emerging: bool = Query(
            True, description="Include emerging signals (signal_score 40–69)"
        ),
    ):
        """
        Cognitive intelligence briefing for a topic.

        Extends /daily-briefing with:
          - so_what:            "Why should I care?" in plain language
          - impact_level:       critical / high / medium / low
          - risk_level:         high / medium / low
          - who_is_affected:    affected companies, countries, institutions, sectors
          - action_implication: what this means for you (rule-based)
          - confidence:         0–100 score based on source count and clustering

        All computation is rule-based. No LLM calls.
        """
        try:
            result = get_daily_cognitive(topic, report_date=date, include_emerging=emerging)
        except Exception as exc:
            _log("cognitive_engine_error_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail="Cognitive engine error. Please try again.",
            )
        return result
