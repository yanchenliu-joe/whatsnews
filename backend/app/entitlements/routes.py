"""
Entitlement routes (Phase 29).

Public (but secret-gated):
  POST /webhooks/revenuecat   — RevenueCat webhook receiver

Auth-gated:
  GET /me/entitlement         — current user's premium status
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from app.auth.deps import get_current_user
from app.auth.models import AuthUser
from app.entitlements.repository import get_entitlement, is_premium, upsert_entitlement
from app.entitlements.webhook import UnparseableEvent, is_valid_user_id, parse_revenuecat_event


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _verify_webhook_secret(authorization: Optional[str]) -> None:
    """
    RevenueCat sends whatever value you configure as the webhook's
    "Authorization header" on every request. Unlike ADMIN_API_KEY (which is
    open when unset, for local admin convenience), a payment webhook always
    requires the secret to be configured — there's no legitimate reason for
    RevenueCat to call a locally-running server, and accepting unauthenticated
    entitlement writes would let anyone grant themselves premium.
    """
    expected = os.getenv("REVENUECAT_WEBHOOK_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="RevenueCat webhook is not configured.")
    if not hmac.compare_digest(authorization or "", expected):
        raise HTTPException(status_code=401, detail="Invalid webhook authorization.")


def register_entitlement_routes(app: FastAPI) -> None:

    @app.post("/webhooks/revenuecat")
    async def revenuecat_webhook(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ):
        _verify_webhook_secret(authorization)

        payload = await request.json()
        try:
            parsed = parse_revenuecat_event(payload)
        except UnparseableEvent as exc:
            _log("revenuecat_webhook_unparseable", error=str(exc)[:200])
            return {"status": "ignored", "reason": str(exc)}

        if not is_valid_user_id(parsed["app_user_id"]):
            # Purchase made before sign-in (RC's own anonymous id). Acknowledge
            # so RevenueCat doesn't retry — Purchases.logIn() after sign-in
            # will cause RC to re-send this under the real user id.
            _log(
                "revenuecat_webhook_anonymous_user",
                event_type=parsed["event_type"],
                app_user_id=parsed["app_user_id"],
            )
            return {"status": "ignored", "reason": "anonymous_app_user_id"}

        try:
            upsert_entitlement(
                parsed["app_user_id"],
                entitlement_id=parsed["entitlement_id"],
                is_active=parsed["is_active"],
                product_id=parsed["product_id"],
                store=parsed["store"],
                expires_at=parsed["expires_at"],
                event_type=parsed["event_type"],
                raw_event=payload,
            )
        except Exception as exc:
            # A user_id that doesn't match any profiles row (FK violation) or a
            # transient DB error both land here. Log and swallow — RevenueCat
            # will retry a 5xx, but a bad user_id will never resolve on retry,
            # so returning 200 avoids infinite retries for that case.
            _log(
                "revenuecat_webhook_persist_error",
                error=str(exc)[:200],
                app_user_id=parsed["app_user_id"],
            )
            return {"status": "error", "reason": "persist_failed"}

        _log(
            "revenuecat_webhook_processed",
            event_type=parsed["event_type"],
            user_id=parsed["app_user_id"],
            is_active=parsed["is_active"],
        )
        return {"status": "ok"}

    @app.get("/me/entitlement")
    def my_entitlement(user: AuthUser = Depends(get_current_user)):
        """Current user's premium status. Requires ENABLE_AUTH=true and a valid session."""
        entitlement = get_entitlement(user.id)
        return {
            "is_premium": is_premium(user.id),
            "entitlement": entitlement,
        }
