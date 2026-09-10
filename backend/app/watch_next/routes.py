"""Watch Next API routes (Phase 17.5)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query

from app.briefing_repository import parse_report_date, validate_report_date
from app.watch_next.service import generate_daily_watch_next, load_watch_next_for_api
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


def register_watch_next_routes(app: FastAPI, require_admin_key) -> None:
    @app.get("/watch-next/latest")
    def get_latest_watch_next():
        """Latest ready Watch Next for the newest publishable briefing date."""
        payload = load_watch_next_for_api()
        if not payload:
            raise HTTPException(status_code=404, detail="No daily briefing report found.")
        if payload.get("status") != "ready":
            raise HTTPException(
                status_code=404,
                detail="No ready Watch Next for the latest briefing date.",
            )
        return payload

    @app.get("/watch-next/daily/{report_date}")
    def get_daily_watch_next(report_date: str):
        """Ready Watch Next for one calendar date."""
        parsed = _parse_date_param(report_date)
        payload = load_watch_next_for_api(parsed)
        if not payload:
            raise HTTPException(
                status_code=404,
                detail=f"No briefing report found for {report_date}.",
            )
        if payload.get("status") != "ready":
            raise HTTPException(
                status_code=404,
                detail=f"No ready Watch Next for {report_date}.",
            )
        return payload

    @app.post("/admin/watch-next/generate")
    def admin_generate_watch_next(
        date_str: Optional[str] = Query(default=None, alias="date"),
        regenerate: bool = Query(default=False),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """Generate daily Watch Next for today or ?date=YYYY-MM-DD."""
        require_admin_key(x_admin_key)

        target: date | None = None
        if date_str:
            target = _parse_date_param(date_str)

        result = generate_daily_watch_next(target, regenerate=regenerate)
        if result.get("status") == "error":
            _log("watch_next_generation_error_failed", error=str(result.get("error")))
            raise HTTPException(
                status_code=503,
                detail="Watch Next generation error. Please try again.",
            )
        return result
