"""Entitlement persistence (Phase 29). Shared DB queries for the entitlements table."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from app.database import get_connection

DEFAULT_ENTITLEMENT_ID = "premium"


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "entitlement_id": row["entitlement_id"],
        "is_active": bool(row["is_active"]),
        "product_id": row.get("product_id"),
        "store": row.get("store"),
        "expires_at": row["expires_at"].isoformat() if row.get("expires_at") else None,
        "last_event_type": row.get("last_event_type"),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def upsert_entitlement(
    user_id: str,
    *,
    entitlement_id: str = DEFAULT_ENTITLEMENT_ID,
    is_active: bool,
    product_id: Optional[str],
    store: Optional[str],
    expires_at: Optional[datetime],
    event_type: Optional[str],
    raw_event: dict[str, Any],
) -> None:
    """Insert or update the entitlement row for one (user_id, entitlement_id) pair."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO entitlements (
                user_id, entitlement_id, is_active, product_id, store,
                expires_at, last_event_type, last_event_at, raw_event, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
            ON CONFLICT (user_id, entitlement_id) DO UPDATE SET
                is_active       = EXCLUDED.is_active,
                product_id      = EXCLUDED.product_id,
                store           = EXCLUDED.store,
                expires_at      = EXCLUDED.expires_at,
                last_event_type = EXCLUDED.last_event_type,
                last_event_at   = NOW(),
                raw_event       = EXCLUDED.raw_event,
                updated_at      = NOW()
            """,
            (
                user_id,
                entitlement_id,
                is_active,
                product_id,
                store,
                expires_at,
                event_type,
                json.dumps(raw_event),
            ),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def get_entitlement(
    user_id: str, entitlement_id: str = DEFAULT_ENTITLEMENT_ID
) -> Optional[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, entitlement_id, is_active, product_id, store,
                   expires_at, last_event_type, updated_at
            FROM entitlements
            WHERE user_id = %s AND entitlement_id = %s
            """,
            (user_id, entitlement_id),
        )
        row = cur.fetchone()
        cur.close()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def is_premium(user_id: str, entitlement_id: str = DEFAULT_ENTITLEMENT_ID) -> bool:
    """
    True when the user has an active, unexpired entitlement.

    A row can remain is_active=TRUE for a short window after expires_at
    passes (until the next webhook, e.g. EXPIRATION, confirms it) — so this
    re-checks expires_at against NOW() in SQL rather than trusting is_active
    alone.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM entitlements
            WHERE user_id = %s
              AND entitlement_id = %s
              AND is_active = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            (user_id, entitlement_id),
        )
        result = cur.fetchone() is not None
        cur.close()
        return result
    finally:
        conn.close()
