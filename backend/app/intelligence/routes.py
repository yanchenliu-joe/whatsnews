"""
Intelligence routes (Phase 25).

Public:
  GET /daily-intelligence?topic=AI[&date=YYYY-MM-DD]

Admin:
  GET /admin/signal-metrics[?date=YYYY-MM-DD]
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import Header, HTTPException, Query

from app.intelligence.service import (
    get_daily_intelligence,
    get_signal_metrics_for_all_topics,
)
from app.log_utils import _log


def register_intelligence_routes(app, require_admin_key):
    @app.get("/daily-intelligence")
    def daily_intelligence(
        topic: str = Query(..., description="Topic name"),
        date: date_type | None = Query(
            None, description="Report date YYYY-MM-DD (defaults to today)"
        ),
    ):
        """
        Signal-scored, event-clustered intelligence briefing for a topic.

        Articles are ranked by signal_score (not recency) and grouped into
        events that cover the same real-world story from multiple sources.

        Noise tier (signal_score < 40) is suppressed from the events list
        and counted in noise_suppressed_count.
        """
        try:
            result = get_daily_intelligence(topic, report_date=date)
        except Exception as exc:
            _log("intelligence_engine_error_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail="Intelligence engine error. Please try again.",
            )
        return result

    @app.get("/admin/signal-metrics")
    def admin_signal_metrics(
        date: date_type | None = Query(
            None, description="Report date YYYY-MM-DD (defaults to today)"
        ),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Cross-topic signal score distribution and source quality metrics.
        Uses today's assembled articles; no new pipeline stage is triggered.

        Protected by ADMIN_API_KEY when that environment variable is set.
        Pass the key via the x-admin-key request header.
        """
        require_admin_key(x_admin_key)
        try:
            result = get_signal_metrics_for_all_topics(target_date=date)
        except Exception as exc:
            _log("signal_metrics_error_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail="Signal metrics error. Please try again.",
            )
        return result
