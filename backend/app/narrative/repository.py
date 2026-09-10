"""Persist and load briefing narratives."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.narrative.audio_config import (
    get_default_voice_profile,
    profile_label,
    VOICE_PROFILE_FEMALE,
    VOICE_PROFILE_MALE,
)
from app.narrative.models import NarrativeScript


def _normalize_audio_url(url: str | None) -> str | None:
    """Return a relative /media/audio path when possible for client-side resolution."""
    if not url:
        return None
    trimmed = url.strip()
    if not trimmed:
        return None
    if trimmed.startswith("/media/audio"):
        return trimmed
    marker = "/media/audio"
    idx = trimmed.find(marker)
    if idx >= 0:
        return trimmed[idx:]
    return trimmed


def _variant_public_dict(profile_id: str, row: dict[str, Any] | None) -> dict[str, Any]:
    label = profile_label(profile_id)
    if not row:
        return {
            "id": profile_id,
            "label": label,
            "status": "not_generated",
            "url": None,
            "duration_seconds": None,
            "generated_at": None,
        }

    generated_at = row.get("audio_generated_at")
    return {
        "id": profile_id,
        "label": label,
        "status": row.get("audio_status") or "not_generated",
        "url": _normalize_audio_url(row.get("audio_url")),
        "duration_seconds": row.get("audio_duration_seconds"),
        "generated_at": generated_at.isoformat() if generated_at else None,
    }


def _legacy_row_as_female_variant(row: dict[str, Any]) -> dict[str, Any] | None:
    if not row.get("audio_url") and (row.get("audio_status") or "not_generated") == "not_generated":
        return None
    return {
        "voice_profile": VOICE_PROFILE_FEMALE,
        "audio_status": row.get("audio_status") or "not_generated",
        "audio_url": row.get("audio_url"),
        "audio_duration_seconds": row.get("audio_duration_seconds"),
        "audio_generated_at": row.get("audio_generated_at"),
    }


def list_audio_variant_rows(cur, narrative_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT *
        FROM narrative_audio_variants
        WHERE narrative_id = %s
        ORDER BY voice_profile
        """,
        (narrative_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_audio_variant_row(cur, narrative_id: int, voice_profile: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM narrative_audio_variants
        WHERE narrative_id = %s AND voice_profile = %s
        """,
        (narrative_id, voice_profile),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def upsert_audio_variant(
    cur,
    narrative_id: int,
    voice_profile: str,
    *,
    audio_status: str,
    audio_url: str | None = None,
    audio_storage_path: str | None = None,
    audio_duration_seconds: int | None = None,
    audio_provider_voice: str | None = None,
    audio_model: str | None = None,
    audio_generated_at: bool = False,
    audio_error_message: str | None = None,
) -> None:
    generated_clause = "NOW()" if audio_generated_at else "narrative_audio_variants.audio_generated_at"

    cur.execute(
        f"""
        INSERT INTO narrative_audio_variants (
            narrative_id,
            voice_profile,
            audio_status,
            audio_url,
            audio_storage_path,
            audio_duration_seconds,
            audio_provider_voice,
            audio_model,
            audio_generated_at,
            audio_error_message,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, {"NOW()" if audio_generated_at else "NULL"}, %s, NOW())
        ON CONFLICT (narrative_id, voice_profile) DO UPDATE SET
            audio_status = EXCLUDED.audio_status,
            audio_url = EXCLUDED.audio_url,
            audio_storage_path = EXCLUDED.audio_storage_path,
            audio_duration_seconds = EXCLUDED.audio_duration_seconds,
            audio_provider_voice = EXCLUDED.audio_provider_voice,
            audio_model = EXCLUDED.audio_model,
            audio_generated_at = {generated_clause},
            audio_error_message = EXCLUDED.audio_error_message,
            updated_at = NOW()
        """,
        (
            narrative_id,
            voice_profile,
            audio_status,
            audio_url,
            audio_storage_path,
            audio_duration_seconds,
            audio_provider_voice,
            audio_model,
            audio_error_message,
        ),
    )


def _build_audio_api_dict(cur, row: dict[str, Any]) -> dict[str, Any]:
    narrative_id = row["id"]
    default_profile = get_default_voice_profile()
    variant_rows = list_audio_variant_rows(cur, narrative_id)
    variant_map = {v["voice_profile"]: v for v in variant_rows}

    if not variant_map and _legacy_row_as_female_variant(row):
        variant_map[VOICE_PROFILE_FEMALE] = _legacy_row_as_female_variant(row)

    variants = [
        _variant_public_dict(VOICE_PROFILE_FEMALE, variant_map.get(VOICE_PROFILE_FEMALE)),
        _variant_public_dict(VOICE_PROFILE_MALE, variant_map.get(VOICE_PROFILE_MALE)),
    ]

    default_variant = next((v for v in variants if v["id"] == default_profile), variants[0])

    return {
        "default_profile": default_profile,
        "variants": variants,
        "status": default_variant["status"],
        "url": default_variant["url"],
        "duration_seconds": default_variant["duration_seconds"],
        "generated_at": default_variant["generated_at"],
    }


def _audio_public_dict(row: dict) -> dict[str, Any]:
    """Legacy audio dict without variants — used only when cur is unavailable."""
    generated_at = row.get("audio_generated_at")
    default_profile = get_default_voice_profile()
    legacy = {
        "status": row.get("audio_status") or "not_generated",
        "url": _normalize_audio_url(row.get("audio_url")),
        "duration_seconds": row.get("audio_duration_seconds"),
        "generated_at": generated_at.isoformat() if generated_at else None,
    }
    variant = _variant_public_dict(default_profile, _legacy_row_as_female_variant(row))
    return {
        "default_profile": default_profile,
        "variants": [
            variant,
            _variant_public_dict(VOICE_PROFILE_MALE, None),
        ],
        **legacy,
    }


def _row_to_api_dict(row: dict, cur: Any | None = None) -> dict[str, Any]:
    script_json = row.get("script_json") or {}
    if isinstance(script_json, str):
        script_json = json.loads(script_json)
    out = dict(script_json)
    out["id"] = row["id"]
    out["status"] = row["status"]
    out["version"] = row["version"]
    out["report_date"] = str(row["report_date"])
    out["scope"] = row["scope"]
    out["script_text"] = row.get("script_text") or ""
    out["plain_text"] = out["script_text"]
    out["word_count"] = row.get("word_count")
    out["estimated_duration_seconds"] = row.get("estimated_duration_seconds")
    out["generation_method"] = row.get("generation_method")
    out["model"] = row.get("model")
    out["error_message"] = row.get("error_message")
    out["generated_at"] = (
        row["generated_at"].isoformat() if row.get("generated_at") else None
    )
    out["article_refs"] = row.get("article_refs") or []
    out["metadata"] = script_json.get("metadata") or {}
    if cur is not None:
        out["audio"] = _build_audio_api_dict(cur, row)
    else:
        out["audio"] = _audio_public_dict(row)
    return out


def get_ready_narrative_row(
    cur,
    report_date: date,
    *,
    scope: str = "daily",
    topic_id: int | None = None,
) -> dict[str, Any] | None:
    """Latest ready narrative row with all DB columns (including audio fields)."""
    cur.execute(
        """
        SELECT *
        FROM briefing_narratives
        WHERE report_date = %s
          AND scope = %s
          AND topic_id IS NOT DISTINCT FROM %s
          AND status = 'ready'
        ORDER BY version DESC
        LIMIT 1
        """,
        (report_date, scope, topic_id),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_ready_narrative(
    cur,
    report_date: date,
    *,
    scope: str = "daily",
    topic_id: int | None = None,
) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM briefing_narratives
        WHERE report_date = %s
          AND scope = %s
          AND topic_id IS NOT DISTINCT FROM %s
          AND status = 'ready'
        ORDER BY version DESC
        LIMIT 1
        """,
        (report_date, scope, topic_id),
    )
    row = cur.fetchone()
    return _row_to_api_dict(dict(row), cur) if row else None


def get_latest_ready_narrative(cur, *, scope: str = "daily") -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM briefing_narratives
        WHERE scope = %s
          AND topic_id IS NULL
          AND status = 'ready'
        ORDER BY report_date DESC, version DESC
        LIMIT 1
        """,
        (scope,),
    )
    row = cur.fetchone()
    return _row_to_api_dict(dict(row), cur) if row else None


def get_next_version(
    cur,
    report_date: date,
    *,
    scope: str = "daily",
    topic_id: int | None = None,
) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(version), 0) AS max_v
        FROM briefing_narratives
        WHERE report_date = %s
          AND scope = %s
          AND topic_id IS NOT DISTINCT FROM %s
        """,
        (report_date, scope, topic_id),
    )
    return int(cur.fetchone()["max_v"]) + 1


def insert_narrative(cur, script: NarrativeScript) -> int:
    script_dict = script.to_dict()
    article_refs = script_dict.get("article_refs") or []

    cur.execute(
        """
        INSERT INTO briefing_narratives (
            report_date,
            scope,
            topic_id,
            version,
            status,
            script_json,
            script_text,
            word_count,
            estimated_duration_seconds,
            article_refs,
            generation_method,
            model,
            error_message,
            generated_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, NOW()
        )
        RETURNING id
        """,
        (
            script.report_date,
            script.scope,
            script.topic_id,
            script.version,
            script.status,
            json.dumps(script_dict),
            script.script_text,
            script.word_count,
            script.estimated_duration_seconds,
            json.dumps(article_refs),
            script.generation_method,
            script.model,
            script.error_message,
            script.generated_at or None,
        ),
    )
    return int(cur.fetchone()["id"])


def update_narrative_audio(
    cur,
    narrative_id: int,
    *,
    audio_status: str,
    audio_url: str | None = None,
    audio_storage_path: str | None = None,
    audio_duration_seconds: int | None = None,
    audio_voice: str | None = None,
    audio_model: str | None = None,
    audio_generated_at: bool = False,
    audio_error_message: str | None = None,
) -> None:
    """Update audio columns and merge audio block into script_json."""
    generated_clause = "NOW()" if audio_generated_at else "audio_generated_at"

    cur.execute(
        f"""
        UPDATE briefing_narratives
        SET
            audio_status = %s,
            audio_url = %s,
            audio_storage_path = %s,
            audio_duration_seconds = %s,
            audio_voice = %s,
            audio_model = %s,
            audio_generated_at = {generated_clause},
            audio_error_message = %s,
            updated_at = NOW(),
            script_json = jsonb_set(
                COALESCE(script_json, '{{}}'::jsonb),
                '{{audio}}',
                %s::jsonb,
                true
            )
        WHERE id = %s
        """,
        (
            audio_status,
            audio_url,
            audio_storage_path,
            audio_duration_seconds,
            audio_voice,
            audio_model,
            audio_error_message,
            json.dumps(
                {
                    "status": audio_status,
                    "url": audio_url,
                    "duration_seconds": audio_duration_seconds,
                    "generated_at": None,
                    "voice": audio_voice,
                    "model": audio_model,
                }
            ),
            narrative_id,
        ),
    )
