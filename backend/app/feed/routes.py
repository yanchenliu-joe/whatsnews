"""
Unified feed routes (Phase 28 / Phase 28B).

Public endpoints:
  GET /feed             — product endpoint; backend decides mode automatically
  GET /daily-feed       — explicit-mode endpoint (internal / power users)

All existing endpoints remain for backward compatibility.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from fastapi import Header, HTTPException, Query, Request

from app.feed.service import get_daily_feed, get_auto_feed, VALID_MODES, clear_feed_cache
from app.log_utils import _log


def register_feed_routes(app, require_admin_key):

    # ── Product endpoint — backend decides everything ─────────────────────────
    @app.get("/feed")
    def feed(
        topic: str = Query(..., description="Topic name"),
        date: date_type | None = Query(
            None, description="Report date YYYY-MM-DD (defaults to latest available)"
        ),
        request: Request = None,
    ):
        """
        Product-facing daily intelligence feed.

        The backend automatically selects the intelligence depth based on:
          - X-Client-Type: mobile header (takes priority)
          - Client type (User-Agent): mobile → cognitive, desktop → briefing
          - Topic category: investor/market topics → cognitive
          - Fallback: briefing

        When the selected mode returns 0 items, a fallback chain is tried:
          cognitive → briefing → signal → raw

        When no date is provided, the latest available report date is used.

        Frontend supplies only topic + date.
        All mode and date decisions are explained in the meta block.
        """
        ua = request.headers.get("user-agent") if request else None
        client_type = request.headers.get("x-client-type") if request else None
        try:
            result = get_auto_feed(
                topic,
                report_date=date,
                user_agent=ua,
                client_type=client_type,
            )
        except Exception as exc:
            _log("feed_engine_error_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail="Feed engine error. Please try again.",
            )
        return result

    # ── Explicit-mode endpoint — internal / power users ───────────────────────
    @app.get("/daily-feed")
    def daily_feed(
        topic: str = Query(..., description="Topic name"),
        mode: str = Query(
            "auto",
            description=(
                "Intelligence depth: auto, raw, signal, briefing, cognitive"
            ),
        ),
        date: date_type | None = Query(
            None, description="Report date YYYY-MM-DD (defaults to today)"
        ),
    ):
        """
        Explicit-mode feed (internal).

        Prefer GET /feed for all product usage — mode selection is automatic there.
        Use this endpoint for debugging, comparison, or admin tooling.
        """
        if mode not in VALID_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode '{mode}'. Valid: {sorted(VALID_MODES)}",
            )
        try:
            result = get_daily_feed(topic, mode=mode, report_date=date)
        except Exception as exc:
            _log("feed_engine_error_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail="Feed engine error. Please try again.",
            )
        return result

    # ── Admin: clear in-memory feed cache ─────────────────────────────────────
    @app.post("/admin/feed/cache/clear")
    def admin_clear_feed_cache(x_admin_key: Optional[str] = Header(default=None)):
        """
        Protected by ADMIN_API_KEY when that environment variable is set.
        Pass the key via the x-admin-key request header.
        """
        require_admin_key(x_admin_key)
        n = clear_feed_cache()
        return {"cleared": n, "status": "ok"}
