"""Voice briefing alignment between daily reports, narratives, and audio."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.briefing_repository import get_latest_daily_report_date
from app.narrative.audio_config import (
    audio_enabled_in_scheduler,
    get_default_voice_profile,
    profile_label,
    VOICE_PROFILE_FEMALE,
    VOICE_PROFILE_MALE,
)


VOICE_STATUS_READY = "ready_for_current_report"
VOICE_STATUS_NARRATIVE_MISSING = "narrative_missing"
VOICE_STATUS_AUDIO_MISSING = "audio_missing"
VOICE_STATUS_AUDIO_DISABLED = "audio_generation_disabled"
VOICE_STATUS_STALE = "stale_audio"
VOICE_STATUS_FAILED = "failed"


def _empty_variants() -> list[dict[str, Any]]:
    return [
        {
            "id": VOICE_PROFILE_FEMALE,
            "label": profile_label(VOICE_PROFILE_FEMALE),
            "status": "not_generated",
            "url": None,
            "duration_seconds": None,
            "generated_at": None,
        },
        {
            "id": VOICE_PROFILE_MALE,
            "label": profile_label(VOICE_PROFILE_MALE),
            "status": "not_generated",
            "url": None,
            "duration_seconds": None,
            "generated_at": None,
        },
    ]


def build_empty_audio_api_dict() -> dict[str, Any]:
    default_profile = get_default_voice_profile()
    return {
        "default_profile": default_profile,
        "variants": _empty_variants(),
        "status": "not_generated",
        "url": None,
        "duration_seconds": None,
        "generated_at": None,
    }


def get_latest_ready_narrative_date(cur, *, scope: str = "daily") -> date | None:
    cur.execute(
        """
        SELECT MAX(report_date) AS latest
        FROM briefing_narratives
        WHERE scope = %s
          AND topic_id IS NULL
          AND status = 'ready'
        """,
        (scope,),
    )
    row = cur.fetchone()
    latest = row["latest"] if row else None
    return latest if latest else None


def get_latest_ready_audio_date(cur, *, scope: str = "daily") -> date | None:
    cur.execute(
        """
        SELECT MAX(bn.report_date) AS latest
        FROM briefing_narratives bn
        JOIN narrative_audio_variants nav ON nav.narrative_id = bn.id
        WHERE bn.scope = %s
          AND bn.topic_id IS NULL
          AND bn.status = 'ready'
          AND nav.audio_status = 'ready'
          AND nav.audio_url IS NOT NULL
        """,
        (scope,),
    )
    row = cur.fetchone()
    latest = row["latest"] if row else None
    if latest:
        return latest

    cur.execute(
        """
        SELECT MAX(report_date) AS latest
        FROM briefing_narratives
        WHERE scope = %s
          AND topic_id IS NULL
          AND status = 'ready'
          AND audio_status = 'ready'
          AND audio_url IS NOT NULL
        """,
        (scope,),
    )
    row = cur.fetchone()
    latest = row["latest"] if row else None
    return latest if latest else None


def _profile_audio_ready(cur, narrative_id: int, voice_profile: str) -> bool:
    cur.execute(
        """
        SELECT audio_status, audio_url
        FROM narrative_audio_variants
        WHERE narrative_id = %s AND voice_profile = %s
        """,
        (narrative_id, voice_profile),
    )
    row = cur.fetchone()
    if row and row["audio_status"] == "ready" and row["audio_url"]:
        return True
    return False


def _voice_variants_summary(cur, narrative_id: int) -> dict[str, str]:
    cur.execute(
        """
        SELECT voice_profile, audio_status
        FROM narrative_audio_variants
        WHERE narrative_id = %s
        """,
        (narrative_id,),
    )
    return {r["voice_profile"]: r["audio_status"] for r in cur.fetchall()}


def build_voice_alignment(cur, *, anchor_date: date | None = None) -> dict[str, Any]:
    """
    Compare latest daily report vs narrative/audio for the anchor report date.

    anchor_date defaults to the latest publishable daily report date.
    """
    latest_report = anchor_date or get_latest_daily_report_date(cur)
    latest_ready_narrative = get_latest_ready_narrative_date(cur)
    latest_ready_audio = get_latest_ready_audio_date(cur)
    audio_enabled = audio_enabled_in_scheduler()

    out: dict[str, Any] = {
        "latest_daily_report_date": str(latest_report) if latest_report else None,
        "latest_ready_narrative_date": (
            str(latest_ready_narrative) if latest_ready_narrative else None
        ),
        "latest_ready_audio_date": str(latest_ready_audio) if latest_ready_audio else None,
        "anchor_report_date": str(latest_report) if latest_report else None,
        "audio_generation_enabled": audio_enabled,
        "voice_status": VOICE_STATUS_NARRATIVE_MISSING,
        "message": "No daily briefing report found.",
    }

    if not latest_report:
        return out

    cur.execute(
        """
        SELECT id, status, report_date, audio_status, audio_url, audio_generated_at
        FROM briefing_narratives
        WHERE scope = 'daily'
          AND topic_id IS NULL
          AND report_date = %s
        ORDER BY version DESC
        LIMIT 1
        """,
        (latest_report,),
    )
    narrative_row = cur.fetchone()

    if not narrative_row or narrative_row["status"] != "ready":
        out["voice_status"] = VOICE_STATUS_NARRATIVE_MISSING
        out["message"] = (
            f"No ready narrative for the latest briefing date ({latest_report})."
        )
        return out

    narrative_id = narrative_row["id"]
    default_profile = get_default_voice_profile()
    voice_variants = _voice_variants_summary(cur, narrative_id)
    out["voice_variants"] = voice_variants
    profile_ready = _profile_audio_ready(cur, narrative_id, default_profile)

    if not profile_ready and narrative_row.get("audio_status") == "ready" and narrative_row.get("audio_url"):
        if default_profile == VOICE_PROFILE_FEMALE:
            profile_ready = True

    if profile_ready:
        out["voice_status"] = VOICE_STATUS_READY
        out["message"] = f"Voice audio is ready for {latest_report}."
        return out

    if not audio_enabled:
        out["voice_status"] = VOICE_STATUS_AUDIO_DISABLED
        out["message"] = (
            "Voice audio has not been generated for the latest briefing. "
            "Automatic audio generation is disabled (ENABLE_VOICE_AUDIO_GENERATION=false)."
        )
        return out

    cur.execute(
        """
        SELECT audio_status
        FROM narrative_audio_variants
        WHERE narrative_id = %s
        """,
        (narrative_id,),
    )
    statuses = [r["audio_status"] for r in cur.fetchall()]
    if statuses and any(s == "failed" for s in statuses):
        out["voice_status"] = VOICE_STATUS_FAILED
        out["message"] = f"Voice audio generation failed for {latest_report}."
        return out

    if latest_ready_audio and latest_ready_audio < latest_report:
        out["voice_status"] = VOICE_STATUS_STALE
        out["message"] = (
            f"Voice audio is only ready for {latest_ready_audio}, "
            f"but the latest briefing is {latest_report}."
        )
        return out

    out["voice_status"] = VOICE_STATUS_AUDIO_MISSING
    out["message"] = (
        "Voice audio has not been generated for the latest briefing. "
        "Generate it in Operator Console."
    )
    return out


def build_missing_narrative_api(cur, report_date: date) -> dict[str, Any]:
    alignment = build_voice_alignment(cur, anchor_date=report_date)
    return {
        "id": None,
        "report_date": str(report_date),
        "scope": "daily",
        "status": "missing",
        "version": 0,
        "script_text": "",
        "generated_at": None,
        "audio": build_empty_audio_api_dict(),
        "voice_alignment": alignment,
    }


def get_pipeline_dates_summary(cur) -> dict[str, Any]:
    latest_report = get_latest_daily_report_date(cur)
    latest_narrative = get_latest_ready_narrative_date(cur)
    latest_audio = get_latest_ready_audio_date(cur)
    return {
        "latest_daily_report_date": str(latest_report) if latest_report else None,
        "latest_ready_narrative_date": (
            str(latest_narrative) if latest_narrative else None
        ),
        "latest_ready_audio_date": str(latest_audio) if latest_audio else None,
    }
