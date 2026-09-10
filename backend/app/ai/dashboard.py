"""Admin AI dashboard aggregation."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.ai.health import get_health_snapshot
from app.ai.registry import get_ai_provider, get_provider_name
from app.ai.usage import get_session_usage_snapshot
from app.briefing_repository import get_latest_daily_report_date
from app.narrative.voice_alignment import build_voice_alignment


def _map_narrative_status(raw: str | None) -> str:
    if not raw:
        return "missing"
    if raw == "ready":
        return "ready"
    if raw == "failed":
        return "failed"
    if raw in ("pending", "generating"):
        return "generating"
    return "generating"


def _feature_status(cur, report_date: date | None = None) -> dict[str, Any]:
    """
    Narrative/voice feature status for the admin dashboard.

    Anchored on the latest publishable daily report date (same as GET /narratives/latest).
    """
    anchor = report_date or get_latest_daily_report_date(cur)
    alignment = build_voice_alignment(cur, anchor_date=anchor) if anchor else {
        "voice_status": "narrative_missing",
        "message": "No daily briefing report found.",
        "latest_daily_report_date": None,
        "latest_ready_narrative_date": None,
        "latest_ready_audio_date": None,
        "anchor_report_date": None,
        "audio_generation_enabled": False,
    }

    if not anchor:
        return {
            "narrative_status": "missing",
            "voice_status": alignment["voice_status"],
            "voice_status_detail": alignment.get("message"),
            "report_date": None,
            "narrative_generated_at": None,
            "voice_generated_at": None,
            "version": None,
            "voice_variants": {},
            "dates": {
                "latest_daily_report_date": None,
                "latest_ready_narrative_date": alignment.get("latest_ready_narrative_date"),
                "latest_ready_audio_date": alignment.get("latest_ready_audio_date"),
            },
        }

    cur.execute(
        """
        SELECT id, status, audio_status, report_date, audio_generated_at, generated_at, version
        FROM briefing_narratives
        WHERE scope = 'daily'
          AND topic_id IS NULL
          AND report_date = %s
        ORDER BY version DESC
        LIMIT 1
        """,
        (anchor,),
    )
    row = cur.fetchone()

    voice_variants: dict[str, str] = {}
    narrative_id = row["id"] if row else None
    if narrative_id:
        cur.execute(
            """
            SELECT voice_profile, audio_status
            FROM narrative_audio_variants
            WHERE narrative_id = %s
            """,
            (narrative_id,),
        )
        voice_variants = {r["voice_profile"]: r["audio_status"] for r in cur.fetchall()}

    return {
        "narrative_status": _map_narrative_status(row["status"] if row else None),
        "voice_status": alignment["voice_status"],
        "voice_status_detail": alignment.get("message"),
        "report_date": str(anchor),
        "narrative_generated_at": (
            row["generated_at"].isoformat() if row and row.get("generated_at") else None
        ),
        "voice_generated_at": (
            row["audio_generated_at"].isoformat() if row and row.get("audio_generated_at") else None
        ),
        "version": row.get("version") if row else None,
        "voice_variants": voice_variants,
        "dates": {
            "latest_daily_report_date": alignment.get("latest_daily_report_date"),
            "latest_ready_narrative_date": alignment.get("latest_ready_narrative_date"),
            "latest_ready_audio_date": alignment.get("latest_ready_audio_date"),
        },
        "audio_generation_enabled": alignment.get("audio_generation_enabled"),
        "voice_variants": alignment.get("voice_variants") or voice_variants,
    }


def _db_counts(cur) -> dict[str, int]:
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM briefing_narratives
        WHERE scope = 'daily'
          AND topic_id IS NULL
          AND status = 'ready'
          AND generated_at >= CURRENT_DATE
        """
    )
    narrative_today = int(cur.fetchone()["count"])

    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM briefing_narratives
        WHERE scope = 'daily'
          AND topic_id IS NULL
          AND audio_status = 'ready'
          AND audio_generated_at >= CURRENT_DATE
        """
    )
    tts_today = int(cur.fetchone()["count"])

    cur.execute(
        """
        SELECT COALESCE(SUM(ai_refine_success_count), 0) AS count
        FROM generation_runs
        WHERE started_at >= CURRENT_DATE
        """
    )
    wim_today = int(cur.fetchone()["count"])

    return {
        "narrative_generation_count": narrative_today,
        "tts_generation_count": tts_today,
        "wim_refine_count": wim_today,
    }


def get_ai_dashboard(cur, *, report_date: date | None = None) -> dict[str, Any]:
    provider = get_ai_provider()
    configured = provider.is_configured()
    session = get_session_usage_snapshot()
    db_counts = _db_counts(cur)

    return {
        "provider": get_provider_name(),
        "api_configured": configured,
        "health": get_health_snapshot(api_configured=configured),
        "usage": {
            "today": {
                **db_counts,
                "narrative_refine_count": session["narrative_refine_count"],
                "session_wim_refine_count": session["wim_refine_count"],
                "session_tts_count": session["tts_generation_count"],
                "estimated_cost_usd": session["estimated_cost_usd"],
            },
            "month_to_date_estimated_cost_usd": session["month_to_date_estimated_cost_usd"],
            "cost_note": "Best-effort estimate from model pricing; not billing-accurate.",
        },
        "features": _feature_status(cur, report_date=report_date),
    }
