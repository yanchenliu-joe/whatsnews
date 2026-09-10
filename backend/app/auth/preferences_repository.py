"""User preferences persistence (Phase 18.4)."""

from __future__ import annotations

import json
from typing import Any

import psycopg2

from app.database import get_connection

ALLOWED_PREFERENCE_KEYS = frozenset(
    {
        "default_topic",
        "preferred_voice_profile",
        "push_notifications_enabled",
        "ui_language",
    }
)
ALLOWED_VOICE_PROFILES = frozenset({"female", "male"})

# Phase 38 (2026-07-06) — app UI language switching. zh-Hans/zh-Hant follow
# BCP 47 script subtags (Simplified/Traditional Chinese); ar/ur are RTL.
ALLOWED_UI_LANGUAGES = frozenset(
    {"en", "zh-Hans", "zh-Hant", "es", "pt", "ja", "hi", "ar", "fr", "bn", "ru", "ur"}
)


def _validate_patch(patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("Preferences patch must be a JSON object.")

    validated: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in ALLOWED_PREFERENCE_KEYS:
            raise ValueError(f"Unsupported preference key: {key}")

        if key == "default_topic":
            if value is None:
                validated[key] = None
            elif not isinstance(value, str) or not value.strip():
                raise ValueError("default_topic must be a non-empty string.")
            else:
                validated[key] = value.strip()[:200]

        elif key == "preferred_voice_profile":
            if value is None:
                validated[key] = None
            elif not isinstance(value, str) or value not in ALLOWED_VOICE_PROFILES:
                raise ValueError("preferred_voice_profile must be 'female' or 'male'.")
            else:
                validated[key] = value

        elif key == "push_notifications_enabled":
            if not isinstance(value, bool):
                raise ValueError("push_notifications_enabled must be a boolean.")
            validated[key] = value

        elif key == "ui_language":
            if not isinstance(value, str) or value not in ALLOWED_UI_LANGUAGES:
                raise ValueError(
                    f"ui_language must be one of: {sorted(ALLOWED_UI_LANGUAGES)}"
                )
            validated[key] = value

    return validated


def _normalize_preferences(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in ALLOWED_PREFERENCE_KEYS:
        if key not in raw:
            continue
        try:
            normalized[key] = _validate_patch({key: raw[key]})[key]
        except ValueError:
            continue
    return normalized


def get_user_preferences(user_id: str) -> dict[str, Any]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT preferences, updated_at
            FROM user_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()

        if not row:
            return {"preferences": {}, "updated_at": None}

        return {
            "preferences": _normalize_preferences(row["preferences"]),
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        }
    except psycopg2.Error as e:
        raise RuntimeError(f"Preferences database error: {e}") from e
    finally:
        conn.close()


def patch_user_preferences(user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    validated = _validate_patch(patch)
    if not validated:
        raise ValueError("At least one valid preference field is required.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_preferences (user_id, preferences, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                preferences = user_preferences.preferences || EXCLUDED.preferences,
                updated_at = NOW()
            RETURNING preferences, updated_at
            """,
            (user_id, json.dumps(validated)),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f"Preferences database error: {e}") from e
    finally:
        conn.close()

    if not row:
        raise RuntimeError("Preferences patch returned no row.")

    return {
        "preferences": _normalize_preferences(row["preferences"]),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }
