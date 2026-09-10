"""Profile persistence for authenticated users."""

from __future__ import annotations

import psycopg2

from app.auth.models import AuthUser, UserProfile
from app.database import get_connection


def _default_display_name(user: AuthUser) -> str | None:
    if user.user_metadata:
        for key in ("full_name", "name", "display_name"):
            value = user.user_metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if user.email and "@" in user.email:
        return user.email.split("@", 1)[0]
    return None


def _default_avatar_url(user: AuthUser) -> str | None:
    if not user.user_metadata:
        return None
    for key in ("avatar_url", "picture"):
        value = user.user_metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_or_create_profile(user: AuthUser) -> UserProfile:
    """
    Return the user's profile row, creating or refreshing it from JWT claims.
    Requires migration 0012 (profiles table).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO profiles (id, email, display_name, avatar_url, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                email = COALESCE(EXCLUDED.email, profiles.email),
                display_name = COALESCE(profiles.display_name, EXCLUDED.display_name),
                avatar_url = COALESCE(profiles.avatar_url, EXCLUDED.avatar_url),
                updated_at = NOW()
            RETURNING id, email, display_name, avatar_url, created_at
            """,
            (
                user.id,
                user.email,
                _default_display_name(user),
                _default_avatar_url(user),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f"Profile database error: {e}") from e
    finally:
        conn.close()

    if not row:
        raise RuntimeError("Profile upsert returned no row.")

    return UserProfile(
        id=str(row["id"]),
        email=row.get("email"),
        display_name=row.get("display_name"),
        avatar_url=row.get("avatar_url"),
        created_at=row["created_at"].isoformat() if row.get("created_at") else None,
    )


def update_avatar_url(user_id: str, avatar_url: str) -> UserProfile:
    """
    Set a user-uploaded avatar (Phase 37, added 2026-07-06). Deliberately a
    plain overwrite, NOT the COALESCE pattern in get_or_create_profile() —
    that one protects the OAuth-populated default from being clobbered by
    stale JWT claims on every request; this is an explicit user action that
    should always take effect. Requires migration 0025 (avatars bucket) for
    the URL to actually resolve, but doesn't depend on it structurally —
    this just persists whatever URL the client already uploaded to.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE profiles
            SET avatar_url = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, email, display_name, avatar_url, created_at
            """,
            (avatar_url, user_id),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f"Profile database error: {e}") from e
    finally:
        conn.close()

    if not row:
        raise ValueError("Profile not found.")

    return UserProfile(
        id=str(row["id"]),
        email=row.get("email"),
        display_name=row.get("display_name"),
        avatar_url=row.get("avatar_url"),
        created_at=row["created_at"].isoformat() if row.get("created_at") else None,
    )
