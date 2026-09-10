"""
RevenueCat webhook event parsing (Phase 29).

RevenueCat POSTs a JSON body shaped like:
  { "api_version": "1.0", "event": { "type": "...", "app_user_id": "...", ... } }

Reference: https://www.revenuecat.com/docs/integrations/webhooks/event-types-and-fields

This module is pure parsing/decision logic — no DB, no HTTP — so it's testable
without mocking anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

# Event types that unambiguously mean "no longer entitled."
_DEACTIVATING_EVENT_TYPES = frozenset({"EXPIRATION"})

DEFAULT_ENTITLEMENT_ID = "premium"


class UnparseableEvent(Exception):
    """Raised when the webhook payload doesn't have the expected shape."""


def _ms_to_datetime(ms: Optional[int]) -> Optional[datetime]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("UTC"))


def parse_revenuecat_event(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Extract the fields we care about from a RevenueCat webhook payload.

    Returns a dict: app_user_id, event_type, entitlement_id, product_id,
    store, expires_at (datetime | None), is_active (bool).

    Raises UnparseableEvent if `event` or `event.app_user_id` is missing —
    callers should return 200 anyway (so RevenueCat doesn't retry a payload
    it will never be able to parse) but skip persisting it.
    """
    event = payload.get("event")
    if not isinstance(event, dict):
        raise UnparseableEvent("Missing 'event' object in webhook payload.")

    app_user_id = event.get("app_user_id")
    if not app_user_id:
        raise UnparseableEvent("Missing 'event.app_user_id' in webhook payload.")

    event_type = event.get("type", "")

    entitlement_ids = event.get("entitlement_ids") or []
    entitlement_id = entitlement_ids[0] if entitlement_ids else DEFAULT_ENTITLEMENT_ID

    expires_at = _ms_to_datetime(event.get("expiration_at_ms"))

    if event_type in _DEACTIVATING_EVENT_TYPES:
        is_active = False
    elif expires_at is not None:
        is_active = expires_at > datetime.now(tz=ZoneInfo("UTC"))
    else:
        # Non-expiring entitlement (e.g. lifetime/non-consumable) with no
        # expiration timestamp — treat any non-deactivating event as active.
        is_active = True

    return {
        "app_user_id": str(app_user_id),
        "event_type": event_type,
        "entitlement_id": entitlement_id,
        "product_id": event.get("product_id"),
        "store": event.get("store"),
        "expires_at": expires_at,
        "is_active": is_active,
    }


def is_valid_user_id(app_user_id: str) -> bool:
    """
    True when app_user_id looks like a Supabase auth UUID (our profiles.id)
    rather than a RevenueCat-generated anonymous id (e.g. "$RCAnonymousID:...")
    — which happens when a user purchases before signing in. Those events are
    acknowledged but not persisted; RevenueCat re-sends the entitlement under
    the real user id once the client calls Purchases.logIn() after sign-in.
    """
    import uuid

    try:
        uuid.UUID(app_user_id)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
