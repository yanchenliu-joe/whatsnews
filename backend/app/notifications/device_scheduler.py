"""
Per-device scheduled push delivery (Phase 34) — devices with a
notification_time preference get pushed at their own local time instead of
the instant the pipeline finishes. Also builds the dynamic push copy shared
by both the scheduled-device tick and the immediate-group push after a
pipeline run.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.analytics.events import _record_event
from app.assembly import compute_importance_score
from app.database import get_connection
from app.log_utils import _log
from app.notifications.push import _send_push_to_tokens


def _immediate_group_devices(server_today: date) -> list:
    """
    Devices with no notification_time preference set — these get pushed once
    per day, from whichever pipeline slot finishes first (Phase 34's original
    behavior). With multiple daily slots (added same phase, 2026-07-06), later
    slots that same day must NOT re-push this group — reuses the same
    last_push_sent_date column _run_device_notification_tick() uses for
    scheduled devices, so a device is never pushed twice in one local day
    regardless of which group it's in.
    """
    try:
        conn = get_connection()
    except ValueError:
        _log("push_skipped", reason="no_database")
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, push_token FROM user_devices "
            "WHERE notification_time IS NULL "
            "AND (last_push_sent_date IS NULL OR last_push_sent_date <> %s)",
            (server_today,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        _log("push_failed", error=str(e)[:200])
        return []

    return [{"id": r["id"], "push_token": r["push_token"]} for r in rows]


def _mark_devices_pushed(device_ids: list, server_today: date) -> None:
    """Records that these devices received their once-a-day push for server_today."""
    if not device_ids:
        return
    try:
        conn = get_connection()
        cur = conn.cursor()
        for device_id in device_ids:
            cur.execute(
                "UPDATE user_devices SET last_push_sent_date = %s WHERE id = %s",
                (server_today, device_id),
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        _log("mark_devices_pushed_failed", error=str(e)[:200])


def _todays_report_exists(server_today: date) -> bool:
    """
    Whether a daily_reports row exists for server_today, across any active
    topic. Deliberately narrower than _build_push_copy()'s "most recent
    report regardless of date" query — that query would happily return
    yesterday's report if today's pipeline hasn't run yet, which would be
    unsafe to use as the sole gate for "is today's content ready".
    """
    try:
        conn = get_connection()
    except ValueError:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM daily_reports dr
            JOIN topics t ON t.id = dr.topic_id
            WHERE t.is_active = TRUE AND dr.report_date = %s
            LIMIT 1
            """,
            (server_today,),
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        _log("todays_report_check_failed", error=str(e)[:200])
        return False


def _is_device_due_for_push(
    now_utc: datetime,
    notification_time: str,
    timezone_name: Optional[str],
    last_push_sent_date: Optional[date],
) -> tuple:
    """
    Pure decision function: is this device due for its scheduled push right
    now? Returns (is_due, local_today) — local_today is what the caller
    should store in last_push_sent_date if it sends now. notification_time
    is assumed non-None (callers only invoke this for devices that have one).
    """
    try:
        tz = ZoneInfo(timezone_name) if timezone_name else ZoneInfo(
            os.getenv("SCHEDULER_TIMEZONE", "UTC")
        )
    except Exception:
        tz = ZoneInfo("UTC")

    local_now = now_utc.astimezone(tz)
    local_today = local_now.date()

    if last_push_sent_date == local_today:
        return False, local_today

    try:
        hour, minute = map(int, notification_time.split(":"))
    except Exception:
        return False, local_today

    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local_now >= target, local_today


def _run_device_notification_tick() -> dict:
    """
    One tick of the per-device scheduled push loop (Phase 34). Bails out
    early if today's content isn't ready yet; otherwise sends the same
    dynamic copy _notify_after_pipeline() would use to whichever devices
    with a notification_time preference are due right now, and marks them
    as sent for today so they aren't double-pushed on the next tick.
    """
    server_tz_name = os.getenv("SCHEDULER_TIMEZONE", "UTC")
    try:
        server_tz = ZoneInfo(server_tz_name)
    except Exception:
        server_tz = ZoneInfo("UTC")

    now_utc = datetime.now(tz=ZoneInfo("UTC"))
    server_today = now_utc.astimezone(server_tz).date()

    if not _todays_report_exists(server_today):
        return {"status": "skipped", "reason": "no_report_yet"}

    try:
        conn = get_connection()
    except ValueError:
        return {"status": "skipped", "reason": "no_database"}

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, push_token, notification_time, timezone, last_push_sent_date "
            "FROM user_devices WHERE notification_time IS NOT NULL"
        )
        devices = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        _log("device_push_tick_failed", error=str(e)[:200])
        return {"status": "error", "detail": str(e)[:200]}

    due_ids = []
    due_tokens = []
    local_today_for_id = {}
    for d in devices:
        is_due, local_today = _is_device_due_for_push(
            now_utc, d["notification_time"], d.get("timezone"), d.get("last_push_sent_date")
        )
        if is_due:
            due_ids.append(d["id"])
            due_tokens.append(d["push_token"])
            local_today_for_id[d["id"]] = local_today

    if not due_tokens:
        return {"status": "ok", "sent": 0, "checked": len(devices)}

    title, body, data = _build_push_copy()
    result = _send_push_to_tokens(due_tokens, title, body, data)

    try:
        conn = get_connection()
        cur = conn.cursor()
        for device_id in due_ids:
            cur.execute(
                "UPDATE user_devices SET last_push_sent_date = %s WHERE id = %s",
                (local_today_for_id[device_id], device_id),
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        _log("device_push_tick_mark_sent_failed", error=str(e)[:200])

    _log("device_push_tick_done", due=len(due_tokens), checked=len(devices),
         sent=result.get("sent"))

    if result.get("status") == "ok" and result.get("sent", 0) > 0:
        _record_event("push_sent", metadata_text=f"sent={result['sent']} copy=scheduled")

    return {"status": "ok", "sent": result.get("sent", 0), "checked": len(devices)}


async def _device_notification_scheduler_loop() -> None:
    """
    Independent tick loop delivering the scheduled (per-device notification_time)
    push group. Started unconditionally in lifespan(), same as
    _global_graph_decay_loop() — this is a delivery mechanism, not content
    generation, so it doesn't depend on ENABLE_SCHEDULER.
    """
    interval = int(os.getenv("DEVICE_PUSH_TICK_SECONDS", "300"))
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(_run_device_notification_tick)
        except Exception as exc:
            _log("device_push_tick_error", error=str(exc)[:200])


_FALLBACK_PUSH_COPY = ("WhatsNews", "Your daily briefing is ready.", None)


def _build_push_copy() -> tuple:
    """
    Build dynamic push notification copy from the newest report's top story.
    Returns (title, body, data). `data` is {"url": ..., "topic": ...} for the
    mobile app's notification-tap deep link (added 2026-07-05), or None when
    falling back to fixed copy (no specific article to link to).
    """
    try:
        conn = get_connection()
    except ValueError:
        return _FALLBACK_PUSH_COPY

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT t.name AS topic_name, dr.id AS report_id
            FROM topics t
            JOIN daily_reports dr ON dr.topic_id = t.id
            WHERE t.is_active = TRUE
            ORDER BY dr.report_date DESC
            LIMIT 1
            """
        )
        report = cur.fetchone()
        if not report:
            cur.close()
            conn.close()
            return _FALLBACK_PUSH_COPY

        cur.execute(
            """
            SELECT title, summary, why_it_matters, url
            FROM articles
            WHERE report_id = %s
            ORDER BY id ASC
            LIMIT 10
            """,
            (report["report_id"],),
        )
        articles = cur.fetchall()
        cur.close()
        conn.close()

        if not articles:
            return _FALLBACK_PUSH_COPY

        topic_name = report["topic_name"]
        top = max(
            articles,
            key=lambda a: compute_importance_score(
                a["title"], a.get("summary") or "", topic_name
            ),
        )

        headline = (top["title"] or "").strip()
        if not headline:
            return _FALLBACK_PUSH_COPY

        # Build body: headline + first sentence of why_it_matters if short enough
        wim = (top.get("why_it_matters") or "").strip()
        if wim:
            first_sentence = wim.split(".")[0].strip()
            candidate = f"{headline} — {first_sentence}."
            body = candidate if len(candidate) <= 178 else headline
        else:
            body = headline

        if len(body) > 178:
            body = body[:175] + "..."

        article_url = (top.get("url") or "").strip()
        data = {"url": article_url, "topic": topic_name} if article_url else None

        return ("WhatsNews", body, data)

    except Exception as e:
        _log("push_copy_failed", error=str(e)[:200])
        return _FALLBACK_PUSH_COPY
