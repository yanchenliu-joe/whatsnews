"""
Entitlements — server-side premium status (Phase 29).

Tracks RevenueCat subscription state keyed by Supabase auth user id
(profiles.id), kept in sync via the RevenueCat webhook.

Public API:
  is_premium(user_id) -> bool
"""

from app.entitlements.repository import get_entitlement, is_premium, upsert_entitlement

__all__ = ["is_premium", "get_entitlement", "upsert_entitlement"]
