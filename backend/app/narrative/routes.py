"""Narrative script API routes."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query

from app.briefing_repository import parse_report_date, validate_report_date
from app.narrative.audio_config import list_voice_profiles_payload
from app.narrative.service import generate_daily_narrative, load_narrative_for_api
from app.narrative.audio_service import generate_narrative_audio
from app.ai.errors import AIErrorCategory, category_public_message
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


def register_narrative_routes(app: FastAPI, require_admin_key) -> None:
    """Attach /narratives* endpoints. require_admin_key is main._require_admin_key."""

    @app.get("/narratives/latest")
    def get_latest_narrative():
        """
        Latest daily morning narrative anchored on the newest publishable briefing date.

        Returns a ready narrative for that date, or a structured missing state when the
        latest briefing has no ready script yet. Does not fall back to older ready audio.
        """
        narrative = load_narrative_for_api(scope="daily")
        if not narrative:
            raise HTTPException(
                status_code=404,
                detail="No daily briefing report found.",
            )
        return narrative

    @app.get("/narratives/daily/{report_date}")
    def get_daily_narrative(report_date: str):
        """
        Ready daily morning narrative for one calendar date.
        404 until status is ready.
        """
        parsed = _parse_date_param(report_date)
        narrative = load_narrative_for_api(parsed, scope="daily")
        if not narrative:
            raise HTTPException(
                status_code=404,
                detail=f"No ready narrative found for {report_date}.",
            )
        return narrative

    @app.get("/narratives/audio/voices")
    def get_narrative_audio_voices():
        """Product-facing voice profiles (Female / Male)."""
        return list_voice_profiles_payload()

    @app.post("/admin/narratives/generate")
    def admin_generate_narrative(
        date_str: Optional[str] = Query(default=None, alias="date"),
        regenerate: bool = Query(default=False),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Generate daily morning narrative for today or ?date=YYYY-MM-DD.

        Skips if a ready script exists unless regenerate=true.
        """
        require_admin_key(x_admin_key)

        target: date | None = None
        if date_str:
            target = _parse_date_param(date_str)

        result = generate_daily_narrative(target, regenerate=regenerate)
        if result.get("status") == "error":
            _log("narrative_generation_error_failed", error=str(result.get("detail")))
            raise HTTPException(status_code=503, detail="Narrative generation error. Please try again.")
        return result

    @app.post("/admin/narratives/audio/generate")
    def admin_generate_narrative_audio(
        date_str: Optional[str] = Query(default=None, alias="date"),
        regenerate: bool = Query(default=False),
        voice_profile: Optional[str] = Query(default=None),
        voice: Optional[str] = Query(default=None),
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Generate TTS audio for a ready daily narrative (today or ?date=YYYY-MM-DD).

        Requires a ready narrative script. Skips if ready audio exists for the same
        voice_profile unless regenerate=true. Legacy voice= accepts provider voice names.
        """
        require_admin_key(x_admin_key)

        target: date | None = None
        if date_str:
            target = _parse_date_param(date_str)

        result = generate_narrative_audio(
            target,
            regenerate=regenerate,
            voice_profile=voice_profile,
            voice=voice,
        )

        if result.get("status") == "error":
            code = result.get("code")
            if code in ("invalid_voice", "invalid_voice_profile"):
                raise HTTPException(status_code=400, detail=result.get("detail", "Invalid voice."))
            if code == "no_api_key":
                raise HTTPException(
                    status_code=503,
                    detail=category_public_message(AIErrorCategory.NOT_CONFIGURED),
                )
            _log("narrative_audio_generation_error_failed", error=str(result.get("detail")))
            raise HTTPException(status_code=503, detail="Audio generation error. Please try again.")

        if result.get("status") == "skipped" and result.get("reason") == "no_ready_narrative":
            raise HTTPException(
                status_code=409,
                detail="No ready narrative found for the requested date.",
            )

        return result
