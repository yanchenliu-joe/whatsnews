"""Daily-mode / interval-mode scheduler loop that drives run_scheduled_pipeline()."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.log_utils import _log
from app.pipeline.orchestrator import _notify_after_pipeline, run_scheduled_pipeline


def seconds_until_next_run(daily_times: list, timezone: str) -> tuple:
    """
    Compute how many seconds until the next scheduled daily run, given one or
    more configured "slot" times in a day (Phase 34, added 2026-07-06 — was a
    single time before this; now supports multiple daily refreshes so content
    stays fresh for users whose notification time is later in the day).

    - daily_times: list of "HH:MM" strings (e.g. ["07:00", "12:00", "18:00"])
    - timezone:    IANA timezone name (e.g. "America/Los_Angeles")

    Returns (seconds_to_wait: float, next_run: datetime) for the SOONEST
    upcoming slot. Any slot whose time has already passed today rolls to
    tomorrow before comparing.
    """
    tz = ZoneInfo(timezone)
    now = datetime.now(tz=tz)

    candidates = []
    for daily_time in daily_times:
        hour, minute = map(int, daily_time.split(":"))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        candidates.append(target)

    next_run = min(candidates)
    return (next_run - now).total_seconds(), next_run


async def scheduler_loop() -> None:
    """
    Unified scheduler loop. Supports two modes:

    Daily mode (primary):
        Set SCHEDULER_DAILY_TIME to one or more comma-separated "HH:MM" slots
        (e.g. "07:00,12:00,18:00") and optionally SCHEDULER_TIMEZONE. Sleeps
        until the next configured slot each time, then runs the full pipeline
        with regenerate=True — every configured slot is a real scheduled
        refresh, so perspective/watch-next/narrative/audio all regenerate
        fresh rather than skipping because "today's" version already exists.

    Interval mode (dev fallback):
        When SCHEDULER_DAILY_TIME is not set, falls back to SCHEDULER_INTERVAL_SECONDS.
        Useful for rapid local testing — kept at regenerate=False (default)
        so rapid iteration doesn't multiply AI/TTS cost on every tick.

    Runs the full pipeline (ingest → assemble → generate) via asyncio.to_thread
    so blocking DB/AI work runs in a thread pool, keeping the event loop free
    to handle HTTP requests in between.

    After a successful pipeline run, sends a push notification to all
    registered devices.  Push failures are logged but never break the loop.
    """
    daily_time = os.getenv("SCHEDULER_DAILY_TIME")

    if daily_time:
        # --- Daily mode ---
        daily_times = [t.strip() for t in daily_time.split(",") if t.strip()]
        timezone = os.getenv("SCHEDULER_TIMEZONE", "UTC")
        while True:
            delay, next_run = seconds_until_next_run(daily_times, timezone)
            _log("scheduler_sleeping_until_next_run",
                 next_run=next_run.strftime("%Y-%m-%d %H:%M %Z"),
                 seconds=round(delay))
            await asyncio.sleep(delay)
            _log("scheduler_run_starting", mode="daily")
            stats = await asyncio.to_thread(run_scheduled_pipeline, True)
            await asyncio.to_thread(_notify_after_pipeline, stats)

    else:
        # --- Interval mode (dev fallback) ---
        interval = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
        while True:
            await asyncio.sleep(interval)
            _log("scheduler_run_starting", mode="interval")
            stats = await asyncio.to_thread(run_scheduled_pipeline)
            await asyncio.to_thread(_notify_after_pipeline, stats)
