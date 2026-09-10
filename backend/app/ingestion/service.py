"""
DB-writing RSS ingestion service for WhatsNews.

Reads active news_sources from the database, fetches RSS feeds, normalises
entries into articles, and inserts them with content_hash deduplication.

This is the original ingestion service (moved here when app/ingestion became a
package in Phase 7.2B).  Its public API is re-exported from app/ingestion/__init__.py
so existing imports such as `from app.ingestion import ingest_all_active_sources`
keep working unchanged.

Run a full ingestion pass with:
    python -m app.ingestion
"""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from app.database import get_connection
from app.ingestion.config import (
    article_scraping_enabled,
    get_ingestion_feed_timeout_seconds,
    get_ingestion_max_concurrency,
    get_ingestion_slow_source_threshold_seconds,
    get_ingestion_topic_concurrency,
    get_scrape_concurrency,
)
from app.ingestion.normalize import improve_summary_from_body, truncate_at_word_boundary
from app.ingestion.scrape import scrape_body_texts_concurrent
from app.ingestion.persist import (
    PersistMetrics,
    persist_source_records,
    prefetch_existing_content_hashes,
)
from app.ingestion.rss import fetch_rss_feed_result

# ── Latest ingestion run state (in-process; resets on restart) ────────────────

_latest_ingestion_run: dict | None = None


def get_latest_ingestion_run() -> dict | None:
    """Return the stats dict from the most recent ingest_all_active_sources call."""
    return _latest_ingestion_run


# ── Logging (matches main.py convention) ──────────────────────────────────────

def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _safe_rollback(conn) -> None:
    """Reset an aborted transaction; no-op if the connection is already closed."""
    try:
        conn.rollback()
    except Exception:
        pass


def _safe_close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_content_hash(title: str, url: str) -> str:
    """SHA-256 of title|url.  Deterministic and collision-safe for MVP."""
    content = f"{title}|{url}"
    return hashlib.sha256(content.encode()).hexdigest()


def build_article_record(article: dict, source_name: str) -> dict:
    """
    Turn a normalized RSS article (from app.ingestion.rss.fetch_rss_feed) into a
    DB-ready row dict.  Computes content_hash, stamps fetched_at, stores the
    original article URL in raw_url, and carries external_id when present.

    `source_name` is the news_sources.name; it overrides the feed-derived
    source so stored articles keep the curated source label the app displays.
    """
    title = (article.get("title") or "")[:500]
    url = (article.get("url") or "")[:2000]
    # Word-boundary-safe — a plain [:2000] slice occasionally landed
    # mid-word (found 2026-07-12: a summary ending "...responsibility. Und"),
    # which is now the *only* text mobile shows for an article (full-text
    # scraping was dropped), so a broken-looking cutoff is a real bug, not
    # cosmetic.
    summary = truncate_at_word_boundary(article.get("summary") or "", 2000)
    body_text = (article.get("body_text") or "")[:8000]
    raw_summary = summary  # the feed's own summary, before any improvement below
    # Rule-based summary improvement (2026-07-13) — always run, even with
    # no body_text at all: improve_summary_from_body() boilerplate-cleans
    # the summary regardless (junk can already be baked into the RSS
    # feed's own summary/description field, not just body_text), and only
    # attempts lengthening when body_text is actually present. RSS
    # full-content feeds populate body_text here already, before any
    # scraping; a separate pass below improves summary again once
    # scraping fills body_text for feeds that only provide a teaser.
    summary = improve_summary_from_body(summary, body_text)

    return {
        "title": title,
        "url": url,
        "source": source_name,
        "summary": summary,
        "body_text": body_text,
        "raw_summary": raw_summary,
        "content_hash": build_content_hash(title, url),
        "fetched_at": datetime.now(tz=ZoneInfo("UTC")),
        "published_at": article.get("published_at"),
        "raw_url": (article.get("raw_url") or url) or None,
        "external_id": article.get("external_id"),
        "image_url": article.get("image_url") or None,
    }


def _build_source_timing_entry(
    *,
    topic_name: str,
    source_name: str,
    feed_url: str,
    duration_seconds: float,
    fetched: int,
    inserted: int,
    skipped: int,
    status: str,
    error: str | None,
) -> dict:
    return {
        "topic": topic_name,
        "source": source_name,
        "feed_url": feed_url,
        "seconds": duration_seconds,
        "duration_seconds": duration_seconds,
        "fetched": fetched,
        "inserted": inserted,
        "skipped": skipped,
        "error": status != "ok",
        "status": status,
        "error_message": error,
    }


def _build_slow_source_entry(timing_entry: dict) -> dict:
    return {
        "topic": timing_entry["topic"],
        "source": timing_entry["source"],
        "feed_url": timing_entry["feed_url"],
        "duration_seconds": timing_entry.get("duration_seconds")
        or timing_entry.get("seconds", 0.0),
        "status": timing_entry.get("status", "error" if timing_entry.get("error") else "ok"),
        "error": timing_entry.get("error_message"),
    }


def _collect_slow_sources(source_timings: list[dict]) -> list[dict]:
    threshold = get_ingestion_slow_source_threshold_seconds()
    slow: list[dict] = []
    for entry in source_timings:
        duration = entry.get("duration_seconds") or entry.get("seconds", 0.0)
        status = entry.get("status", "error" if entry.get("error") else "ok")
        if duration >= threshold or status != "ok":
            slow.append(_build_slow_source_entry(entry))
    slow.sort(key=lambda row: row.get("duration_seconds", 0), reverse=True)
    return slow


_FEED_RETRY_LIMIT = 2          # up to 2 retries (3 total attempts)
_FEED_RETRY_BASE_SECONDS = 1.0  # exponential backoff: 1s, 3s


def _update_feed_reliability(source_id: int, *, success: bool) -> None:
    """
    Update per-feed reliability counters in news_sources after each fetch.
    Auto-disables feeds with consecutive_failures >= 5.
    Auto-re-enables feeds that recover after auto-disable (consecutive_successes >= 3).
    Best-effort: failures here are silently swallowed so they never break ingestion.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            if success:
                cur.execute(
                    """
                    UPDATE news_sources SET
                        success_count         = success_count + 1,
                        consecutive_successes = consecutive_successes + 1,
                        consecutive_failures  = 0,
                        last_success_at       = NOW(),
                        -- Lifecycle: degraded → active after 3 consecutive successes
                        feed_state = CASE
                            WHEN COALESCE(feed_state, 'active') = 'degraded'
                                 AND consecutive_successes + 1 >= 3
                            THEN 'active'
                            WHEN auto_disabled_at IS NOT NULL
                                 AND consecutive_successes + 1 >= 3
                            THEN 'active'
                            ELSE COALESCE(feed_state, 'active')
                        END,
                        -- Re-enable if auto-disabled and recovering
                        is_active = CASE
                            WHEN auto_disabled_at IS NOT NULL
                                 AND consecutive_successes + 1 >= 3
                            THEN TRUE
                            ELSE is_active
                        END,
                        auto_disabled_at = CASE
                            WHEN auto_disabled_at IS NOT NULL
                                 AND consecutive_successes + 1 >= 3
                            THEN NULL
                            ELSE auto_disabled_at
                        END,
                        -- Degraded feeds: skip next run after a successful fetch
                        skip_next_run = CASE
                            WHEN COALESCE(feed_state, 'active') = 'degraded'
                                 AND consecutive_successes + 1 < 3
                            THEN TRUE
                            ELSE FALSE
                        END
                    WHERE id = %s
                    """,
                    (source_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE news_sources SET
                        failure_count         = failure_count + 1,
                        consecutive_failures  = consecutive_failures + 1,
                        consecutive_successes = 0,
                        last_failure_at       = NOW(),
                        -- Lifecycle: active → degraded at 3 consecutive failures
                        feed_state = CASE
                            WHEN COALESCE(feed_state, 'active') = 'active'
                                 AND consecutive_failures + 1 >= 3
                            THEN 'degraded'
                            ELSE COALESCE(feed_state, 'active')
                        END,
                        -- Auto-disable after 5 consecutive failures (with grace period)
                        is_active = CASE
                            WHEN consecutive_failures + 1 >= 5
                                 AND (
                                     success_count > 0
                                     OR created_at < NOW() - INTERVAL '24 hours'
                                 )
                            THEN FALSE
                            ELSE is_active
                        END,
                        auto_disabled_at = CASE
                            WHEN consecutive_failures + 1 >= 5
                                 AND auto_disabled_at IS NULL
                                 AND (
                                     success_count > 0
                                     OR created_at < NOW() - INTERVAL '24 hours'
                                 )
                            THEN NOW()
                            ELSE auto_disabled_at
                        END,
                        skip_next_run = FALSE
                    WHERE id = %s
                    """,
                    (source_id,),
                )
            conn.commit()
        finally:
            cur.close()
            _safe_close(conn)
    except Exception:
        pass  # reliability tracking is never allowed to break ingestion


def _update_feed_reliability_batch(success_ids: list[int], failure_ids: list[int]) -> None:
    """
    Same UPDATE logic as _update_feed_reliability, batched across all sources
    from one fetch pass in a single connection (WHERE id = ANY(%s) instead of
    N per-source connections — added 2026-07-09 after Sentry/profiling showed
    ~300 short-lived connections opened per ingestion run just for this).
    Best-effort: failures here are silently swallowed so they never break
    ingestion, same contract as the per-source version.
    """
    if not success_ids and not failure_ids:
        return
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            if success_ids:
                cur.execute(
                    """
                    UPDATE news_sources SET
                        success_count         = success_count + 1,
                        consecutive_successes = consecutive_successes + 1,
                        consecutive_failures  = 0,
                        last_success_at       = NOW(),
                        feed_state = CASE
                            WHEN COALESCE(feed_state, 'active') = 'degraded'
                                 AND consecutive_successes + 1 >= 3
                            THEN 'active'
                            WHEN auto_disabled_at IS NOT NULL
                                 AND consecutive_successes + 1 >= 3
                            THEN 'active'
                            ELSE COALESCE(feed_state, 'active')
                        END,
                        is_active = CASE
                            WHEN auto_disabled_at IS NOT NULL
                                 AND consecutive_successes + 1 >= 3
                            THEN TRUE
                            ELSE is_active
                        END,
                        auto_disabled_at = CASE
                            WHEN auto_disabled_at IS NOT NULL
                                 AND consecutive_successes + 1 >= 3
                            THEN NULL
                            ELSE auto_disabled_at
                        END,
                        skip_next_run = CASE
                            WHEN COALESCE(feed_state, 'active') = 'degraded'
                                 AND consecutive_successes + 1 < 3
                            THEN TRUE
                            ELSE FALSE
                        END
                    WHERE id = ANY(%s)
                    """,
                    (success_ids,),
                )
            if failure_ids:
                cur.execute(
                    """
                    UPDATE news_sources SET
                        failure_count         = failure_count + 1,
                        consecutive_failures  = consecutive_failures + 1,
                        consecutive_successes = 0,
                        last_failure_at       = NOW(),
                        feed_state = CASE
                            WHEN COALESCE(feed_state, 'active') = 'active'
                                 AND consecutive_failures + 1 >= 3
                            THEN 'degraded'
                            ELSE COALESCE(feed_state, 'active')
                        END,
                        is_active = CASE
                            WHEN consecutive_failures + 1 >= 5
                                 AND (
                                     success_count > 0
                                     OR created_at < NOW() - INTERVAL '24 hours'
                                 )
                            THEN FALSE
                            ELSE is_active
                        END,
                        auto_disabled_at = CASE
                            WHEN consecutive_failures + 1 >= 5
                                 AND auto_disabled_at IS NULL
                                 AND (
                                     success_count > 0
                                     OR created_at < NOW() - INTERVAL '24 hours'
                                 )
                            THEN NOW()
                            ELSE auto_disabled_at
                        END,
                        skip_next_run = FALSE
                    WHERE id = ANY(%s)
                    """,
                    (failure_ids,),
                )
            conn.commit()
        finally:
            cur.close()
            _safe_close(conn)
    except Exception:
        pass  # reliability tracking is never allowed to break ingestion


def _split_success_failure_ids(results: list[dict]) -> tuple[list[int], list[int]]:
    success_ids = [r["source_id"] for r in results if r["status"] == "ok"]
    failure_ids = [r["source_id"] for r in results if r["status"] != "ok"]
    return success_ids, failure_ids


def _fetch_source_job(
    src: dict,
    topic_id: int,
    topic_name: str,
    max_items_per_feed: int | None,
    timeout_seconds: float,
) -> dict:
    """
    Fetch one RSS feed in a worker thread (no DB access during fetch).
    Retries up to _FEED_RETRY_LIMIT times with exponential backoff.
    Does NOT write feed reliability counters itself — the caller batches
    all sources' outcomes into one _update_feed_reliability_batch() call
    after the whole fetch pass completes, instead of one DB connection per
    source (2026-07-09 speed pass).
    """
    _log("ingestion_feed_start", topic=topic_name, source=src["name"])
    last_result = None
    for attempt in range(_FEED_RETRY_LIMIT + 1):
        last_result = fetch_rss_feed_result(
            src["feed_url"],
            max_items=max_items_per_feed,
            timeout_seconds=timeout_seconds,
        )
        if last_result.status == "ok":
            break
        if attempt < _FEED_RETRY_LIMIT:
            sleep_seconds = _FEED_RETRY_BASE_SECONDS * (2 ** attempt)  # 1s, 3s
            time.sleep(sleep_seconds)

    return {
        "topic_id": topic_id,
        "source_id": src["id"],
        "source_name": src["name"],
        "feed_url": src["feed_url"],
        "topic_name": topic_name,
        "articles": last_result.articles,
        "status": last_result.status,
        "error": last_result.error,
        "duration_seconds": last_result.duration_seconds,
        "attempts": attempt + 1,
    }


def fetch_sources_concurrently(
    sources: list[dict],
    topic_name: str,
    max_items_per_feed: int | None = None,
    topic_id: int | None = None,
) -> list[dict]:
    """
    Fetch all RSS feeds for a topic concurrently (bounded by INGESTION_MAX_CONCURRENCY).
    Returns fetch results sorted by source id for deterministic DB write order.
    """
    if not sources:
        return []

    timeout_seconds = get_ingestion_feed_timeout_seconds()
    max_workers = min(len(sources), get_ingestion_max_concurrency())
    resolved_topic_id = topic_id if topic_id is not None else 0
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_source_job,
                src,
                resolved_topic_id,
                topic_name,
                max_items_per_feed,
                timeout_seconds,
            ): src
            for src in sources
        }
        for future in as_completed(futures):
            src = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                results.append(
                    {
                        "topic_id": resolved_topic_id,
                        "source_id": src["id"],
                        "source_name": src["name"],
                        "feed_url": src["feed_url"],
                        "topic_name": topic_name,
                        "articles": [],
                        "status": "error",
                        "error": str(e)[:200],
                        "duration_seconds": 0.0,
                    }
                )

    results.sort(key=lambda row: row["source_id"])
    _update_feed_reliability_batch(*_split_success_failure_ids(results))
    return results


def fetch_all_sources_globally(
    topic_groups: list[dict],
    max_items_per_feed: int | None = None,
) -> tuple[list[dict], float]:
    """
    Fetch RSS feeds for every topic/source in one bounded global pool.
    Returns (flat fetch results, fetch_phase_seconds).
    """
    jobs: list[tuple[dict, int, str]] = []
    for group in topic_groups:
        topic_id = group["topic_id"]
        topic_name = group["topic_name"]
        for src in group["sources"]:
            jobs.append((src, topic_id, topic_name))

    if not jobs:
        return [], 0.0

    timeout_seconds = get_ingestion_feed_timeout_seconds()
    max_workers = min(len(jobs), get_ingestion_max_concurrency())
    fetch_started = time.monotonic()
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _fetch_source_job,
                src,
                topic_id,
                topic_name,
                max_items_per_feed,
                timeout_seconds,
            ): (src, topic_id, topic_name)
            for src, topic_id, topic_name in jobs
        }
        for future in as_completed(futures):
            src, topic_id, topic_name = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                results.append(
                    {
                        "topic_id": topic_id,
                        "source_id": src["id"],
                        "source_name": src["name"],
                        "feed_url": src["feed_url"],
                        "topic_name": topic_name,
                        "articles": [],
                        "status": "error",
                        "error": str(e)[:200],
                        "duration_seconds": 0.0,
                    }
                )

    fetch_seconds = round(time.monotonic() - fetch_started, 2)
    results.sort(key=lambda row: (row["topic_id"], row["source_id"]))
    _update_feed_reliability_batch(*_split_success_failure_ids(results))
    return results, fetch_seconds


def _group_fetch_results_by_topic(fetch_results: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for result in fetch_results:
        grouped.setdefault(result["topic_id"], []).append(result)
    for topic_id in grouped:
        grouped[topic_id].sort(key=lambda row: row["source_id"])
    return grouped


def _load_active_topic_groups(
    topic: str | None = None,
) -> tuple[list[dict], dict]:
    """
    Load active feeds grouped by topic, applying lifecycle throttling.

    Returns:
      (topic_groups, suppression_info) where suppression_info has:
        suppressed_count  — degraded feeds skipped this run
        suppressed_feeds  — list of {topic, name, feed_url, feed_state}

    Lifecycle rules applied here:
      - paused  feeds: always excluded (never auto-fetched)
      - degraded feeds with skip_next_run=TRUE: excluded + flag reset to FALSE
      - degraded feeds with skip_next_run=FALSE: included; flag will be set TRUE after fetch
      - active feeds: always included
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        topic_filter = "AND t.name = %s" if topic else ""
        params = (topic,) if topic else ()
        cur.execute(
            f"""
            SELECT t.id AS topic_id, t.name AS topic_name,
                   ns.id, ns.name, ns.feed_url,
                   COALESCE(ns.feed_state, 'active') AS feed_state,
                   COALESCE(ns.skip_next_run, FALSE)  AS skip_next_run
            FROM topics t
            JOIN news_sources ns
              ON ns.topic_id = t.id
             AND ns.is_active = TRUE
             AND COALESCE(ns.feed_state, 'active') NOT IN ('paused', 'disabled')
            WHERE t.is_active = TRUE {topic_filter}
            ORDER BY t.sort_order ASC, t.name ASC, ns.id ASC
            """,
            params,
        )
        rows = [dict(row) for row in cur.fetchall()]

        # Degraded + skip_next_run=TRUE → suppress this run, reset flag
        suppressed_ids = [
            row["id"] for row in rows
            if row["feed_state"] == "degraded" and row["skip_next_run"]
        ]
        suppressed_feeds = [
            {
                "topic": row["topic_name"],
                "name": row["name"],
                "feed_url": row["feed_url"],
                "feed_state": row["feed_state"],
            }
            for row in rows
            if row["feed_state"] == "degraded" and row["skip_next_run"]
        ]

        if suppressed_ids:
            cur.execute(
                "UPDATE news_sources SET skip_next_run = FALSE WHERE id = ANY(%s)",
                (suppressed_ids,),
            )
            conn.commit()

    finally:
        cur.close()
        _safe_close(conn)

    # Build topic groups from non-suppressed feeds only
    active_ids = set(suppressed_ids)
    groups: dict[int, dict] = {}
    for row in rows:
        if row["id"] in active_ids:
            continue  # suppressed this run
        topic_id = row["topic_id"]
        if topic_id not in groups:
            groups[topic_id] = {
                "topic_id": topic_id,
                "topic_name": row["topic_name"],
                "sources": [],
            }
        groups[topic_id]["sources"].append(
            {
                "id": row["id"],
                "name": row["name"],
                "feed_url": row["feed_url"],
                "feed_state": row["feed_state"],
            }
        )

    suppression_info = {
        "suppressed_count": len(suppressed_ids),
        "suppressed_feeds": suppressed_feeds,
    }
    return list(groups.values()), suppression_info


def _persist_fetch_results(
    conn,
    cur,
    topic_id: int,
    topic_name: str,
    fetch_results: list[dict],
    *,
    apply_scraping: bool = False,
    log_per_feed: bool = False,
) -> tuple[dict, PersistMetrics, list[dict]]:
    """
    Shared core for both ingestion entry points below: builds article records
    from pre-fetched RSS results, prefetches existing content hashes,
    optionally scrapes missing body text, then persists each source's batch
    via persist_source_records() — one commit per source, rolled back and
    skipped on failure so one bad source never blocks the rest of the topic.

    Caller owns `conn`/`cur` (does not open, commit-outside-loop, or close
    them here) and is responsible for filling in timing-derived stats
    (duration_seconds, build_records_seconds, etc.) from the returned
    PersistMetrics — the two callers measure elapsed time differently (one
    already has a separately-measured fetch phase, the other performs its
    own fetch inline before calling this).

    `apply_scraping` and `log_per_feed` preserve an existing, deliberate
    behavior difference between the two callers rather than changing it:
    only the global concurrent ingestion path has ever scraped body text or
    logged per-feed done/failed events; the single-topic on-demand path
    (used by admin_generate_report) never has. See Technical Debt #8.
    """
    stats = {
        "topic": topic_name,
        "sources_processed": 0,
        "articles_fetched": 0,
        "articles_inserted": 0,
        "articles_skipped": 0,
        "errors": 0,
        "source_timings": [],
    }
    topic_metrics = PersistMetrics()
    topic_semantic_samples: list[dict] = []

    pending_sources: list[tuple[dict, list[dict]]] = []
    all_hashes: list[str] = []

    for fetch_result in fetch_results:
        stats["sources_processed"] += 1
        if fetch_result["status"] != "ok":
            stats["errors"] += 1
            stats["source_timings"].append(
                _build_source_timing_entry(
                    topic_name=topic_name,
                    source_name=fetch_result["source_name"],
                    feed_url=fetch_result["feed_url"],
                    duration_seconds=fetch_result["duration_seconds"],
                    fetched=0,
                    inserted=0,
                    skipped=0,
                    status=fetch_result["status"],
                    error=fetch_result.get("error"),
                )
            )
            if log_per_feed:
                _log(
                    "ingestion_feed_failed",
                    topic=topic_name,
                    source=fetch_result["source_name"],
                    status=fetch_result["status"],
                    seconds=fetch_result["duration_seconds"],
                    error=(fetch_result.get("error") or "")[:200],
                )
            continue

        build_started = time.monotonic()
        records = [
            build_article_record(article, source_name=fetch_result["source_name"])
            for article in (fetch_result.get("articles") or [])
        ]
        topic_metrics.build_records_seconds += round(
            time.monotonic() - build_started, 4
        )
        all_hashes.extend(record["content_hash"] for record in records)
        pending_sources.append((fetch_result, records))

    prefetch_started = time.monotonic()
    existing_hashes = prefetch_existing_content_hashes(cur, all_hashes)
    topic_metrics.db_insert_seconds += round(
        time.monotonic() - prefetch_started, 4
    )

    # Scrape full article body text for new records (opt-in via env var).
    # Filtered to content_hashes NOT already in the DB — most RSS items
    # on any given run are re-fetches of already-ingested articles, and
    # scraping their full page body before knowing that just wastes the
    # network round-trip on something about to be discarded as a dup.
    if apply_scraping and article_scraping_enabled():
        to_scrape = [
            record
            for _, records in pending_sources
            for record in records
            if not record.get("body_text")
            and record.get("url")
            and record["content_hash"] not in existing_hashes
        ]
        if to_scrape:
            scraped_map = scrape_body_texts_concurrent(
                to_scrape, max_workers=get_scrape_concurrency()
            )
            if scraped_map:
                for _, records in pending_sources:
                    for record in records:
                        url = record.get("url", "")
                        if not record.get("body_text") and url in scraped_map:
                            record["body_text"] = scraped_map[url]
                            record["summary"] = improve_summary_from_body(
                                record["summary"], record["body_text"]
                            )
                _log(
                    "ingestion_scrape_complete",
                    topic=topic_name,
                    scraped=len(scraped_map),
                    attempted=len(to_scrape),
                )

    for fetch_result, records in pending_sources:
        try:
            persist_result = persist_source_records(
                conn, cur, topic_id, records, existing_hashes,
                collect_semantic_samples=True,
            )
            conn.commit()
        except Exception:
            stats["errors"] += 1
            stats["source_timings"].append(
                _build_source_timing_entry(
                    topic_name=topic_name,
                    source_name=fetch_result["source_name"],
                    feed_url=fetch_result["feed_url"],
                    duration_seconds=fetch_result["duration_seconds"],
                    fetched=len(records),
                    inserted=0,
                    skipped=0,
                    status="error",
                    error="commit failed",
                )
            )
            _safe_rollback(conn)
            continue

        topic_metrics.merge(persist_result.metrics)
        stats["errors"] += persist_result.errors
        stats["articles_fetched"] += len(records)
        stats["articles_inserted"] += persist_result.inserted
        stats["articles_skipped"] += persist_result.skipped
        topic_semantic_samples.extend(persist_result.semantic_samples)
        stats["source_timings"].append(
            _build_source_timing_entry(
                topic_name=topic_name,
                source_name=fetch_result["source_name"],
                feed_url=fetch_result["feed_url"],
                duration_seconds=fetch_result["duration_seconds"],
                fetched=len(records),
                inserted=persist_result.inserted,
                skipped=persist_result.skipped,
                status="ok",
                error=None,
            )
        )
        if log_per_feed:
            _log(
                "ingestion_feed_done",
                topic=topic_name,
                source=fetch_result["source_name"],
                fetched=len(records),
                inserted=persist_result.inserted,
                skipped=persist_result.skipped,
                seconds=fetch_result["duration_seconds"],
            )

    return stats, topic_metrics, topic_semantic_samples


def _persist_topic_fetch_results(
    topic_id: int,
    topic_name: str,
    fetch_results: list[dict],
) -> dict:
    """Write pre-fetched RSS results for one topic using an isolated DB connection."""
    conn = get_connection()
    cur = conn.cursor()
    persist_started = time.monotonic()

    try:
        stats, topic_metrics, topic_semantic_samples = _persist_fetch_results(
            conn, cur, topic_id, topic_name, fetch_results,
            apply_scraping=True, log_per_feed=True,
        )

        fetch_span = max(
            (row["duration_seconds"] for row in fetch_results),
            default=0.0,
        )
        stats["duration_seconds"] = round(
            fetch_span + (time.monotonic() - persist_started),
            2,
        )
        stats["build_records_seconds"] = round(topic_metrics.build_records_seconds, 2)
        stats["db_insert_seconds"] = round(topic_metrics.db_insert_seconds, 2)
        stats["duplicate_skip_count"] = topic_metrics.duplicate_skip_count
        stats["semantic_skip_count"] = topic_metrics.semantic_skip_count
        stats["batch_count"] = topic_metrics.batch_count
        stats["semantic_samples"] = topic_semantic_samples[:20]
        return stats
    finally:
        cur.close()
        _safe_close(conn)


# ── Per-topic ingestion ───────────────────────────────────────────────────────

def ingest_sources_for_topic(
    conn,
    topic_id: int,
    topic_name: str,
    max_items_per_feed: int | None = None,
) -> dict:
    """
    Run ingestion for one topic: fetches every active source's RSS feed,
    normalises entries, and inserts new articles linked to the topic.
    Articles are stored as raw candidates — no daily_report is created here.

    RSS feeds are fetched concurrently (Phase 15.1); DB writes remain sequential
    per source on the caller's connection.

    Returns a per-topic stats dict.  Caller owns the connection and must close it.
    On commit failure, rolls back and re-raises so the caller can close and continue.
    """
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT id, name, feed_url
            FROM news_sources
            WHERE topic_id = %s AND is_active = TRUE
            ORDER BY id ASC
            """,
            (topic_id,),
        )
        sources = [dict(r) for r in cur.fetchall()]

        topic_started = time.monotonic()
        fetch_results = fetch_sources_concurrently(
            sources,
            topic_name,
            max_items_per_feed=max_items_per_feed,
            topic_id=topic_id,
        )

        stats, topic_metrics, topic_semantic_samples = _persist_fetch_results(
            conn, cur, topic_id, topic_name, fetch_results,
            apply_scraping=False, log_per_feed=False,
        )

        stats["duration_seconds"] = round(time.monotonic() - topic_started, 2)
        stats["build_records_seconds"] = round(topic_metrics.build_records_seconds, 2)
        stats["db_insert_seconds"] = round(topic_metrics.db_insert_seconds, 2)
        stats["duplicate_skip_count"] = topic_metrics.duplicate_skip_count
        stats["semantic_skip_count"] = topic_metrics.semantic_skip_count
        stats["batch_count"] = topic_metrics.batch_count
        stats["semantic_samples"] = topic_semantic_samples[:20]
        return stats
    finally:
        cur.close()


# ── Full ingestion pass ───────────────────────────────────────────────────────

def ingest_all_active_sources(
    topic: str | None = None,
    max_items_per_feed: int | None = None,
) -> dict:
    """
    Run a full ingestion pass over every active topic and its active sources.
    Opens a fresh database connection per topic so a failure in one topic
    cannot poison ingestion for the rest.

    Optional dev-only filters (CLI):
      topic              — ingest only this topic name; all active topics if omitted
      max_items_per_feed — cap articles processed per feed after RSS parsing

    Returns aggregate stats:
      topics_processed, sources_processed, sources_checked, articles_fetched,
      articles_inserted, articles_skipped, errors_count, duration_ms,
      duration_seconds, topic_seconds, source_timings, slow_sources
    """
    started = time.monotonic()
    _log(
        "ingestion_started",
        topic=topic,
        max_items=max_items_per_feed,
        max_concurrency=get_ingestion_max_concurrency(),
        topic_concurrency=get_ingestion_topic_concurrency(),
        feed_timeout_seconds=get_ingestion_feed_timeout_seconds(),
    )

    _empty_return = {
        "topics_processed": 0,
        "sources_processed": 0,
        "sources_checked": 0,
        "articles_fetched": 0,
        "articles_inserted": 0,
        "articles_skipped": 0,
        "errors_count": 1,
        "duration_ms": 0,
        "duration_seconds": 0.0,
        "topic_seconds": {},
        "source_timings": [],
        "slow_sources": [],
        "suppression_count": 0,
    }
    try:
        topic_groups, suppression_info = _load_active_topic_groups(topic=topic)
    except ValueError as e:
        _log("ingestion_aborted", reason=str(e))
        return _empty_return

    if topic and not topic_groups:
        _log("ingestion_aborted", reason=f"topic_not_found:{topic}")
        return _empty_return

    suppression_count = suppression_info.get("suppressed_count", 0)
    if suppression_count:
        _log(
            "ingestion_throttled",
            suppressed_count=suppression_count,
            reason="degraded_feeds_skip_next_run",
        )

    totals = {
        "topics_processed": 0,
        "sources_processed": 0,
        "sources_checked": 0,
        "articles_fetched": 0,
        "articles_inserted": 0,
        "articles_skipped": 0,
        "errors_count": 0,
        "topic_seconds": {},
        "source_timings": [],
        "slow_sources": [],
        "build_records_seconds": 0.0,
        "db_insert_seconds": 0.0,
        "duplicate_skip_count": 0,
        "semantic_skip_count": 0,
        "batch_count": 0,
        "semantic_sample_duplicates": [],
        "suppression_count": suppression_count,
        "suppressed_feeds": suppression_info.get("suppressed_feeds", []),
    }

    fetch_results, fetch_phase_seconds = fetch_all_sources_globally(
        topic_groups,
        max_items_per_feed=max_items_per_feed,
    )
    grouped_results = _group_fetch_results_by_topic(fetch_results)

    persist_started = time.monotonic()
    topic_workers = min(len(topic_groups), get_ingestion_topic_concurrency())

    def _persist_topic_group(group: dict) -> tuple[dict, dict | None, str | None]:
        topic_id = group["topic_id"]
        topic_name = group["topic_name"]
        try:
            topic_stats = _persist_topic_fetch_results(
                topic_id,
                topic_name,
                grouped_results.get(topic_id, []),
            )
            return group, topic_stats, None
        except Exception as e:
            return group, None, str(e)[:200]

    with ThreadPoolExecutor(max_workers=topic_workers) as executor:
        futures = [
            executor.submit(_persist_topic_group, group)
            for group in topic_groups
        ]
        for future in as_completed(futures):
            group, topic_stats, error = future.result()
            topic_name = group["topic_name"]
            if error or topic_stats is None:
                totals["errors_count"] += 1
                _log("ingestion_topic_error", topic=topic_name, error=error or "unknown")
                continue

            totals["topics_processed"] += 1
            totals["sources_processed"] += topic_stats["sources_processed"]
            totals["articles_fetched"] += topic_stats["articles_fetched"]
            totals["articles_inserted"] += topic_stats["articles_inserted"]
            totals["articles_skipped"] += topic_stats["articles_skipped"]
            totals["errors_count"] += topic_stats["errors"]
            totals["topic_seconds"][topic_name] = topic_stats.get("duration_seconds", 0.0)
            totals["source_timings"].extend(topic_stats.get("source_timings") or [])
            totals["build_records_seconds"] += topic_stats.get("build_records_seconds", 0.0)
            totals["db_insert_seconds"] += topic_stats.get("db_insert_seconds", 0.0)
            totals["duplicate_skip_count"] += topic_stats.get("duplicate_skip_count", 0)
            totals["semantic_skip_count"] += topic_stats.get("semantic_skip_count", 0)
            totals["batch_count"] += topic_stats.get("batch_count", 0)
            totals["semantic_sample_duplicates"].extend(
                topic_stats.get("semantic_samples") or []
            )

            _log(
                "ingestion_topic_done",
                topic=topic_name,
                inserted=topic_stats["articles_inserted"],
                skipped=topic_stats["articles_skipped"],
                seconds=topic_stats.get("duration_seconds"),
            )

    persist_phase_seconds = round(time.monotonic() - persist_started, 2)

    duration_ms = int((time.monotonic() - started) * 1000)
    totals["duration_ms"] = duration_ms
    totals["duration_seconds"] = round(duration_ms / 1000.0, 2)
    totals["sources_checked"] = totals["sources_processed"]
    totals["slow_sources"] = _collect_slow_sources(totals["source_timings"])

    # Compute feed success/failure breakdown from source_timings
    failed_feed_timings = [t for t in totals["source_timings"] if t.get("status") != "ok"]
    totals["feeds_checked"] = len(totals["source_timings"])
    totals["feeds_success"] = len(totals["source_timings"]) - len(failed_feed_timings)
    totals["feeds_failed"] = len(failed_feed_timings)
    totals["failed_feeds"] = [
        {
            "topic": t.get("topic", ""),
            "feed_name": t.get("source", ""),
            "feed_url": t.get("feed_url", ""),
            "error": t.get("error_message") or t.get("status", "error"),
        }
        for t in failed_feed_timings
    ]

    # Cap semantic samples globally
    totals["semantic_sample_duplicates"] = totals["semantic_sample_duplicates"][:20]
    totals["semantic_duplicates_skipped"] = totals["semantic_skip_count"]
    totals["hard_duplicates_skipped"] = totals["duplicate_skip_count"]

    # Timestamps for the latest-run endpoint
    totals["started_at"] = datetime.fromtimestamp(
        time.time() - totals["duration_seconds"], tz=ZoneInfo("UTC")
    ).isoformat()
    totals["finished_at"] = datetime.now(tz=ZoneInfo("UTC")).isoformat()
    totals["fetch_phase_seconds"] = fetch_phase_seconds
    totals["persist_phase_seconds"] = persist_phase_seconds
    totals["build_records_seconds"] = round(totals["build_records_seconds"], 2)
    totals["db_insert_seconds"] = round(totals["db_insert_seconds"], 2)

    _log(
        "ingestion_completed",
        topics=totals["topics_processed"],
        inserted=totals["articles_inserted"],
        skipped=totals["articles_skipped"],
        errors=totals["errors_count"],
        feeds_success=totals["feeds_success"],
        feeds_failed=totals["feeds_failed"],
        semantic_duplicates_skipped=totals["semantic_duplicates_skipped"],
        hard_duplicates_skipped=totals["hard_duplicates_skipped"],
        duration_ms=duration_ms,
        duration_seconds=totals["duration_seconds"],
        fetch_phase_seconds=fetch_phase_seconds,
        persist_phase_seconds=persist_phase_seconds,
        build_records_seconds=totals["build_records_seconds"],
        db_insert_seconds=totals["db_insert_seconds"],
        batch_count=totals["batch_count"],
        slow_source_count=len(totals["slow_sources"]),
        slowest_source=(
            totals["slow_sources"][0]["source"]
            if totals["slow_sources"]
            else None
        ),
        slowest_seconds=(
            totals["slow_sources"][0]["duration_seconds"]
            if totals["slow_sources"]
            else None
        ),
    )

    # Compute feed state distribution from DB for this run's snapshot
    try:
        _conn = get_connection()
        _cur = _conn.cursor()
        _cur.execute(
            """
            SELECT COALESCE(feed_state, 'active') AS state, COUNT(*) AS cnt
            FROM news_sources
            GROUP BY state
            """
        )
        totals["feed_state_distribution"] = {
            row["state"]: row["cnt"] for row in _cur.fetchall()
        }
        _cur.close()
        _safe_close(_conn)
    except Exception:
        totals["feed_state_distribution"] = {}

    global _latest_ingestion_run
    _latest_ingestion_run = totals

    return totals
