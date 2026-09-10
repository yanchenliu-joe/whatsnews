"""
Independent background maintenance/warmup loops started unconditionally
from lifespan() — none of these depend on ENABLE_SCHEDULER, and none of
them share any state with each other or with the content pipeline.
"""

from __future__ import annotations

import asyncio

from app.database import get_connection
from app.feed.service import get_auto_feed as _get_auto_feed
from app.log_utils import _log
from app.retention.config import get_cleanup_tick_seconds
from app.retention.service import run_archive_cleanup


async def _global_graph_decay_loop() -> None:
    """Phase 23D: periodic temporal decay + global influence recomputation.

    Strict pipeline (executed immediately on startup, then every 600 s):
      1. apply_decay()    — recompute decay_weight per node
      2. compute_scores() — global_score = influence_score × decay_weight
      3. sleep 600 s

    ORDERING IS LOCKED: decay BEFORE compute, sleep AFTER.
    No other calls to apply_decay() or compute_scores() exist outside this loop.
    """
    from app.ai.global_graph import global_graph as _gg
    _log("global_graph_decay_loop", status="started", interval_s=600)
    while True:
        try:
            _gg.apply_decay()       # step 1: recompute decay_weight per node
            _gg.compute_scores()    # step 2: global_score = influence_score × decay_weight
            stats = _gg.stats()
            _log(
                "global_graph_decay",
                nodes=stats["total_nodes"],
                edges=stats["total_edges"],
            )
        except Exception as exc:
            _log("global_graph_decay_error", error=str(exc)[:200])
        await asyncio.sleep(600)   # step 3: wait 10 minutes before next cycle


async def _archive_cleanup_loop() -> None:
    """
    Deletes daily-report-scoped data (articles, narratives, perspectives,
    watch-next, generation_runs, narrative audio files) older than
    ARCHIVE_RETENTION_DAYS (default 7) — keeps Supabase storage bounded
    instead of growing forever. Started unconditionally in lifespan(), same
    as _global_graph_decay_loop() — a maintenance job, not content
    generation, so it doesn't depend on ENABLE_SCHEDULER.

    Runs immediately on startup (not after the first sleep) — deliberately
    different from _device_notification_scheduler_loop()'s sleep-first
    pattern, since Render redeploys restart this process periodically and a
    24h default interval could otherwise go a long time between real runs
    if the process rarely stays up for a full day.
    """
    interval = get_cleanup_tick_seconds()
    while True:
        try:
            await asyncio.to_thread(run_archive_cleanup)
        except Exception as exc:
            _log("archive_cleanup_loop_error", error=str(exc)[:200])
        await asyncio.sleep(interval)


async def _feed_cache_warmup() -> None:
    """Background task: pre-warm /feed cache for all active topics after startup."""
    await asyncio.sleep(5)  # Let the server finish startup before hitting the DB
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM topics WHERE is_active = true ORDER BY sort_order")
        topics = [row["name"] for row in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as exc:
        print(f"[whatsnews] event=feed_cache_warmup_error stage=topics error={str(exc)[:120]}")
        return

    loop = asyncio.get_event_loop()

    async def _warm_one(topic: str) -> None:
        try:
            await loop.run_in_executor(None, lambda t=topic: _get_auto_feed(t, client_type="mobile"))
        except Exception as exc:
            print(f"[whatsnews] event=feed_cache_warmup_error topic={topic} error={str(exc)[:80]}")

    await asyncio.gather(*[_warm_one(t) for t in topics])
    print(f"[whatsnews] event=feed_cache_warmup_complete topics={len(topics)}")
