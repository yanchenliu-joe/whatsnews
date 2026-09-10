"""Editorial perspective API routes (Phase 17.3)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query

from app.briefing_repository import parse_report_date, validate_report_date
from app.perspective.service import generate_daily_perspective, load_perspective_for_api
from app.log_utils import _log


def _parse_date_param(report_date: str) -> date:
    try:
        parsed = parse_report_date(report_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD.")
    try:
        validate_report_date(parsed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return parsed


def register_perspective_routes(app: FastAPI, require_admin_key) -> None:
    @app.get("/perspectives/latest")
    def get_latest_perspective():
        """Latest ready editorial perspective for the newest publishable briefing date."""
        perspective = load_perspective_for_api()
        if not perspective:
            raise HTTPException(status_code=404, detail="No daily briefing report found.")
        if perspective.get("status") != "ready":
            raise HTTPException(
                status_code=404,
                detail="No ready editorial perspective for the latest briefing date.",
            )
        return perspective

    @app.get("/perspectives/daily/{report_date}")
    def get_daily_perspective(report_date: str):
        """Ready editorial perspective for one calendar date."""
        parsed = _parse_date_param(report_date)
        perspective = load_perspective_for_api(parsed)
        if not perspective:
            raise HTTPException(
                status_code=404,
                detail=f"No briefing report found for {report_date}.",
            )
        if perspective.get("status") != "ready":
            raise HTTPException(
                status_code=404,
                detail=f"No ready editorial perspective for {report_date}.",
            )
        return perspective

    @app.post("/admin/perspectives/generate")
    def admin_generate_perspective(
        date_str: Optional[str] = Query(default=None, alias="date"),
        regenerate: bool = Query(default=False),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """Generate daily editorial perspective for today or ?date=YYYY-MM-DD."""
        require_admin_key(x_admin_key)

        target: date | None = None
        if date_str:
            target = _parse_date_param(date_str)

        result = generate_daily_perspective(target, regenerate=regenerate)
        if result.get("status") == "error":
            _log("perspective_generation_error_failed", error=str(result.get("error")))
            raise HTTPException(
                status_code=503,
                detail="Perspective generation error. Please try again.",
            )
        return result
