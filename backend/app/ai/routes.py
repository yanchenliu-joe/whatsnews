"""Admin AI platform routes."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query

from app.ai.dashboard import get_ai_dashboard
from app.ai.debug import debug_openai_responses, debug_tts_synthesis
from app.ai.errors import AIErrorCategory
from app.ai.health import clear_health_simulation, simulate_health_status
from app.log_utils import _log


def register_ai_admin_routes(app: FastAPI, require_admin_key) -> None:
    @app.get("/admin/ai-status")
    def admin_ai_status(
        date_str: Optional[str] = Query(default=None, alias="date"),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """AI health, usage estimates, and feature status for Operator Console."""
        require_admin_key(x_admin_key)

        target: date | None = None
        if date_str:
            try:
                target = date.fromisoformat(date_str)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date. Use YYYY-MM-DD.")

        from app.database import get_connection

        try:
            conn = get_connection()
        except ValueError as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        cur = conn.cursor()
        try:
            return get_ai_dashboard(cur, report_date=target)
        finally:
            cur.close()
            conn.close()

    @app.post("/admin/ai-health/simulate")
    def admin_simulate_ai_health(
        scenario: str = Query(...),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Simulate AI health states for Operator Console verification.

        scenario: healthy | invalid_api_key | insufficient_quota | rate_limit | timeout | provider_error | clear
        """
        require_admin_key(x_admin_key)

        mapping = {
            "healthy": ("healthy", None),
            "clear": ("healthy", None),
            "invalid_api_key": ("unavailable", AIErrorCategory.INVALID_API_KEY),
            "insufficient_quota": ("unavailable", AIErrorCategory.INSUFFICIENT_QUOTA),
            "rate_limit": ("degraded", AIErrorCategory.RATE_LIMIT),
            "timeout": ("degraded", AIErrorCategory.TIMEOUT),
            "provider_error": ("warning", AIErrorCategory.PROVIDER_ERROR),
        }

        if scenario not in mapping:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scenario. Valid: {', '.join(sorted(mapping))}",
            )

        if scenario in ("healthy", "clear"):
            clear_health_simulation()
            return {"status": "ok", "simulated": "healthy"}

        status, category = mapping[scenario]
        simulate_health_status(status, category=category)
        return {"status": "ok", "simulated": status, "category": category.value if category else None}

    @app.get("/admin/debug/openai")
    def admin_debug_openai(x_admin_key: Optional[str] = Header(default=None)):
        """Temporary: minimal OpenAI Responses API connectivity check."""
        require_admin_key(x_admin_key)
        return debug_openai_responses()

    @app.post("/admin/debug/tts")
    def admin_debug_tts(
        text: str = Query(default="Hello from WhatsNews."),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """Temporary: TTS-only check using narrative synthesize_speech()."""
        require_admin_key(x_admin_key)
        return debug_tts_synthesis(text)
