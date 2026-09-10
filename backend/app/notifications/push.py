"""Expo Push API senders — the low-level "send to these tokens" primitives."""

from __future__ import annotations

from typing import Optional

import httpx

from app.database import get_connection
from app.log_utils import _log

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _send_push_to_tokens(tokens: list, title: str, body: str, data: Optional[dict] = None) -> dict:
    """
    Send a push notification to a given list of Expo push tokens.

    `data` (added 2026-07-05) is delivered as the notification's payload and
    read by the mobile app's notification-tap handler to deep-link straight to
    the article, instead of just opening the app to the default screen.

    Never raises — all errors are caught and returned in the result dict.
    Safe to call from the scheduler without risking pipeline stability.
    """
    if not tokens:
        _log("push_skipped", reason="no_devices")
        return {"status": "skipped", "sent": 0, "detail": "No registered devices."}

    messages = [
        {"to": token, "sound": "default", "title": title, "body": body, "data": data or {}}
        for token in tokens
    ]

    _log("push_sending", device_count=len(tokens))

    try:
        resp = httpx.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        _log("push_failed", error=str(e)[:200])
        return {"status": "error", "detail": str(e)[:500]}

    tickets = result.get("data", [])
    ok_count = sum(1 for t in tickets if t.get("status") == "ok")
    error_count = len(tickets) - ok_count

    _log("push_complete", sent=ok_count, errors=error_count)

    return {
        "status": "ok",
        "sent": ok_count,
        "errors": error_count,
        "tickets": tickets,
    }


def _send_push_to_all_devices(title: str, body: str, data: Optional[dict] = None) -> dict:
    """
    Send a push notification to every registered device via Expo Push API.
    Used by admin's "send test push" action, which deliberately blasts
    everyone regardless of each device's notification_time preference.
    """
    try:
        conn = get_connection()
    except ValueError:
        _log("push_skipped", reason="no_database")
        return {"status": "skipped", "detail": "DATABASE_URL not configured."}

    try:
        cur = conn.cursor()
        cur.execute("SELECT push_token FROM user_devices")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        _log("push_failed", error=str(e)[:200])
        return {"status": "error", "detail": f"Database error: {e}"}

    return _send_push_to_tokens([r["push_token"] for r in rows], title, body, data)
