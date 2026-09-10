"""
Daily briefing routes (Phase 26).

Public:
  GET /daily-briefing?topic=AI[&date=YYYY-MM-DD][&emerging=true]

No admin-gated endpoints in this module — briefing is a public product layer.
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import HTTPException, Query

from app.briefing.service import get_daily_briefing
from app.log_utils import _log


def register_briefing_routes(app):
    @app.get("/daily-briefing")
    def daily_briefing(
        topic: str = Query(..., description="Topic name"),
        date: date_type | None = Query(
            None, description="Report date YYYY-MM-DD (defaults to today)"
        ),
        emerging: bool = Query(
            True, description="Include emerging signals appendix (40–69 signal score)"
        ),
    ):
        """
        Narrative intelligence briefing for a topic.

        Returns events transformed into structured narrative blocks:
        - headline: ≤18-word neutral statement
        - what_happened: factual synthesis from sources
        - why_it_matters: significance interpretation
        - what_changed: delta from prior state
        - watch_next: forward-looking structured inference

        Main briefing: signal_score ≥ 70 (up to 8 items)
        Emerging signals: signal_score 40–69 (up to 5 items, optional)
        Noise: signal_score < 40 — completely excluded

        Cross-event threads identify when multiple stories share a key entity.
        """
        try:
            result = get_daily_briefing(topic, report_date=date, include_emerging=emerging)
        except Exception as exc:
            _log("briefing_engine_error_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail="Briefing engine error. Please try again.",
            )
        return result
