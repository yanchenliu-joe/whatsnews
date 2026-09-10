"""
Unified feed service (Phase 28 / Phase 28B / V1-hotfix).

Two entry points:
  get_daily_feed(topic, mode, date)              — explicit mode (/daily-feed, debug)
  get_auto_feed(topic, date, user_agent, …)      — backend-decided mode (/feed, product)

Auto-selection rules (/feed):
  X-Client-Type: mobile header                → cognitive
  investor topics (Markets, Finance…)         → cognitive
  mobile User-Agent                           → cognitive
  desktop / unknown                           → briefing

Fallback chain (V1-hotfix):
  When the selected mode returns 0 items, try the remaining modes in order:
    cognitive → briefing → signal → raw
  The first non-empty result is returned.

Date resolution (V1-hotfix):
  When no date is provided, the latest available report date for the topic
  is used instead of blindly defaulting to today.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.database import get_connection
from app.intelligence.service import get_daily_intelligence
from app.briefing.service import get_daily_briefing
from app.cognitive.service import get_daily_cognitive
from app.feed.normalizer import (
    normalize_raw,
    normalize_signal,
    normalize_briefing,
    normalize_cognitive,
)

VALID_MODES = frozenset({"auto", "raw", "signal", "briefing", "cognitive"})

_NOISE_REDUCING_MODES = frozenset({"signal", "briefing", "cognitive"})

# Fallback order when selected mode returns zero items.
_FALLBACK_CHAIN = ["cognitive", "briefing", "signal", "raw"]

# ── In-memory caches (/feed only) ────────────────────────────────────────────

# Response cache — full feed result, keyed by "topic|date|mode_selected"
_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 300  # seconds

# Date resolution cache — avoids a DB round-trip on every cache hit.
# TTL is intentionally shorter than the response cache so a new pipeline
# run within the same 5-minute window is picked up promptly.
_DATE_CACHE: dict[str, tuple[date, float]] = {}
_DATE_CACHE_TTL = 60  # seconds


def _cache_key(topic: str, resolved_date: date, mode_selected: str) -> str:
    return f"{topic}|{resolved_date.isoformat()}|{mode_selected}"


def _cache_get(key: str) -> dict | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    response, expires_at = entry
    if time.monotonic() > expires_at:
        del _CACHE[key]
        return None
    return response


def _cache_set(key: str, response: dict) -> None:
    _CACHE[key] = (response, time.monotonic() + _CACHE_TTL)


def clear_feed_cache() -> int:
    n = len(_CACHE)
    _CACHE.clear()
    _DATE_CACHE.clear()
    return n


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


# ── Date resolution ───────────────────────────────────────────────────────────

def _resolve_report_date(topic: str, requested: date | None) -> tuple[date, bool]:
    """
    Return (resolved_date, date_fallback_applied).

    If `requested` is given, return it as-is (date_fallback_applied=False).
    If not given, return the latest available report date for the topic,
    using a short-lived cache to avoid a DB round-trip on every request.
    Falls back to today when no report exists.
    """
    if requested is not None:
        return requested, False

    # Fast path: date cache hit (avoids DB on cache hits)
    dc = _DATE_CACHE.get(topic)
    if dc is not None:
        cached_date, expires_at = dc
        if time.monotonic() < expires_at:
            return cached_date, True

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT MAX(dr.report_date) AS latest
            FROM daily_reports dr
            JOIN topics t ON t.id = dr.topic_id
            WHERE t.name = %s
            """,
            (topic,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row["latest"]:
            _DATE_CACHE[topic] = (row["latest"], time.monotonic() + _DATE_CACHE_TTL)
            return row["latest"], True
    except Exception as exc:
        _log("feed_date_resolve_error", topic=topic, error=str(exc)[:120])

    return datetime.now(tz=ZoneInfo("UTC")).date(), False


# ── Mode helpers ──────────────────────────────────────────────────────────────

def _build_fallback_chain(selected: str) -> list[str]:
    """Return modes to try in order: selected first, then the rest of the chain."""
    chain = [selected]
    for mode in _FALLBACK_CHAIN:
        if mode != selected:
            chain.append(mode)
    return chain


def _resolve_mode(requested: str) -> str:
    """Expand 'auto' to the concrete best-available mode."""
    if requested == "auto":
        return "cognitive"
    return requested


ALL_TOPIC_NAME = "All"
ALL_TOPIC_LIMIT = 200  # max articles in cross-topic feed (10 per topic × ~20 topics)


# ── All-topics mode: top articles across every active topic ───────────────────

def _get_all_topics_articles(report_date: date) -> dict:
    """
    Fetch the top ALL_TOPIC_LIMIT assembled articles across all active topics
    for the given date, sorted by editorial importance then recency.
    Each article row includes `topic_name` for display on the client.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id, a.title, a.url, a.summary, a.body_text, a.source,
                a.why_it_matters, a.published_at, a.editorial_metadata,
                a.image_url, t.name AS topic_name
            FROM articles a
            JOIN daily_reports dr ON a.report_id = dr.id
            JOIN topics t ON dr.topic_id = t.id
            WHERE dr.report_date = %s AND t.is_active = TRUE
            ORDER BY
                COALESCE((a.editorial_metadata->>'importance_score')::numeric, 0) DESC,
                a.published_at DESC NULLS LAST
            LIMIT %s
            """,
            (report_date, ALL_TOPIC_LIMIT),
        )
        articles = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        if not articles:
            return {"available": False, "topic": ALL_TOPIC_NAME, "articles": []}
        return {
            "available": True,
            "topic": ALL_TOPIC_NAME,
            "report_date": report_date.isoformat(),
            "articles": articles,
        }
    except Exception as e:
        _log("feed_all_topics_db_error", error=str(e)[:200])
        return {"available": False, "topic": ALL_TOPIC_NAME, "articles": []}


# ── Raw mode: read assembled articles directly from DB ────────────────────────

def _get_raw_articles(topic: str, report_date: date | None, now: datetime) -> dict:
    """
    Minimal DB query for raw mode: returns assembled articles for the report.
    No signal scoring, no clustering.
    """
    target = report_date or now.date()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dr.report_date, t.name AS topic_name
            FROM daily_reports dr
            JOIN topics t ON t.id = dr.topic_id
            WHERE t.name = %s AND dr.report_date = %s
            LIMIT 1
            """,
            (topic, target),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return {"available": False, "topic": topic, "articles": []}

        cur.execute(
            """
            SELECT id, title, url, summary, body_text, source, why_it_matters,
                   published_at, editorial_metadata, image_url
            FROM articles
            WHERE report_id = (
                SELECT dr.id FROM daily_reports dr
                JOIN topics t ON t.id = dr.topic_id
                WHERE t.name = %s AND dr.report_date = %s
                LIMIT 1
            )
            ORDER BY published_at DESC NULLS LAST
            """,
            (topic, target),
        )
        articles = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()

        return {
            "available": True,
            "topic": row["topic_name"],
            "report_date": target.isoformat(),
            "articles": articles,
        }
    except Exception as e:
        _log("feed_raw_db_error", topic=topic, error=str(e)[:200])
        return {"available": False, "topic": topic, "articles": []}


# ── Per-mode loader (shared by both entry points) ─────────────────────────────

def _load_for_mode(
    mode: str,
    topic: str,
    report_date: date,
) -> tuple[list[dict], dict]:
    """
    Load and normalize items for one intelligence mode.
    Returns (items, raw_data_dict).
    """
    now = datetime.now(tz=ZoneInfo("UTC"))
    if topic == ALL_TOPIC_NAME:
        data = _get_all_topics_articles(report_date)
        return normalize_raw(data), data
    if mode == "raw":
        data = _get_raw_articles(topic, report_date, now)
        return normalize_raw(data), data
    if mode == "signal":
        data = get_daily_intelligence(topic, report_date=report_date)
        return normalize_signal(data), data
    if mode == "briefing":
        data = get_daily_briefing(topic, report_date=report_date, include_emerging=True)
        return normalize_briefing(data), data
    # cognitive (and any unrecognised alias)
    data = get_daily_cognitive(topic, report_date=report_date, include_emerging=True)
    return normalize_cognitive(data), data


# ── Unified feed (explicit mode, /daily-feed) ─────────────────────────────────

def get_daily_feed(
    topic: str,
    mode: str = "auto",
    report_date: date | None = None,
) -> dict:
    """
    Unified feed for one topic at the requested intelligence depth.
    mode=auto selects the deepest available layer (cognitive).
    All existing endpoints remain unchanged; this is a routing layer only.
    """
    if mode not in VALID_MODES:
        return {
            "error": f"Invalid mode '{mode}'. Valid modes: {sorted(VALID_MODES)}",
        }

    resolved_mode = _resolve_mode(mode)
    now = datetime.now(tz=ZoneInfo("UTC"))
    t_start = now

    items, data = _load_for_mode(resolved_mode, topic, report_date or now.date())

    elapsed_ms = round(
        (datetime.now(tz=ZoneInfo("UTC")) - t_start).total_seconds() * 1000, 1
    )

    available = data.get("available", True)

    _log(
        "feed_served",
        topic=topic,
        mode=resolved_mode,
        items=len(items),
        latency_ms=elapsed_ms,
        available=available,
    )

    return {
        "topic":     data.get("topic", topic),
        "mode_used": resolved_mode,
        "available": available,
        "items":     items,
        "meta": {
            "generation_mode":         resolved_mode,
            "requested_mode":          mode,
            "latency_ms":              elapsed_ms,
            "noise_reduction_applied": resolved_mode in _NOISE_REDUCING_MODES,
            "total_items":             len(items),
            "report_date":             data.get("report_date"),
        },
    }


# ── Auto-selection engine (/feed endpoint) ────────────────────────────────────

_MOBILE_RE = re.compile(
    r"(Android|iPhone|iPad|iPod|webOS|BlackBerry|Windows Phone|Mobile)",
    re.IGNORECASE,
)

# Topics where investors expect full cognitive analysis
_INVESTOR_TOPIC_KEYWORDS = frozenset({
    "market", "finance", "financial", "economics", "economy",
    "cryptocurrency", "crypto", "stocks", "stock", "investing",
    "investment", "banking", "monetary", "interest rate", "inflation",
    "currency", "forex", "commodities", "commodity",
})


def _select_mode(
    topic: str,
    user_agent: str | None,
    client_type: str | None = None,
) -> tuple[str, str]:
    """
    Decide which intelligence mode to use for the /feed endpoint.
    Returns (mode, mode_reason).

    Priority:
      1. X-Client-Type: mobile header
      2. Investor / market topic keywords
      3. Mobile User-Agent
      4. Desktop User-Agent
      5. No hint → briefing (safe default)
    """
    # Explicit mobile header takes priority over User-Agent detection
    if client_type and client_type.lower() == "mobile":
        return (
            "cognitive",
            "X-Client-Type: mobile → cognitive mode for maximum per-item insight.",
        )

    topic_lower = topic.lower()

    # Investor / market topics → always cognitive
    for kw in _INVESTOR_TOPIC_KEYWORDS:
        if kw in topic_lower:
            return (
                "cognitive",
                "Investor-grade topic detected → cognitive mode for full analysis.",
            )

    # Mobile User-Agent → cognitive
    if user_agent and _MOBILE_RE.search(user_agent):
        return (
            "cognitive",
            "Mobile User-Agent detected → cognitive mode for maximum per-item insight.",
        )

    # Desktop or unidentified → briefing (more scannable on larger screens)
    if user_agent:
        return (
            "briefing",
            "Desktop client → briefing mode for structured narrative.",
        )

    # No User-Agent (API clients, curl, internal) → briefing
    return (
        "briefing",
        "No client hint → briefing mode as safe default.",
    )


def get_auto_feed(
    topic: str,
    report_date: date | None = None,
    user_agent: str | None = None,
    client_type: str | None = None,
) -> dict:
    """
    Product-facing feed with backend-decided intelligence mode and fallback chain.

    Called exclusively by GET /feed.  The frontend supplies only topic + date;
    all mode logic lives here.

    V1-hotfix additions:
      - Resolves latest available report date when no date is provided.
      - Tries the selected mode first; if it returns 0 items, walks the
        fallback chain (cognitive → briefing → signal → raw) until items are found.
      - Checks X-Client-Type header before User-Agent for client type detection.
      - Returns rich debug meta on every response.
    """
    t_start = time.monotonic()

    # Special path: cross-topic "All" feed — skip mode selection, go straight to raw
    if topic == ALL_TOPIC_NAME:
        if report_date:
            resolved_date = report_date
        else:
            # Find the latest available report date across all active topics
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT MAX(dr.report_date) AS latest
                    FROM daily_reports dr
                    JOIN topics t ON t.id = dr.topic_id
                    WHERE t.is_active = TRUE
                    """
                )
                row = cur.fetchone()
                cur.close()
                conn.close()
                resolved_date = row["latest"] if row and row["latest"] else datetime.now(tz=ZoneInfo("UTC")).date()
            except Exception as exc:
                _log("feed_all_date_resolve_error", error=str(exc)[:120])
                resolved_date = datetime.now(tz=ZoneInfo("UTC")).date()
        ck = _cache_key(topic, resolved_date, "raw")
        cached = _cache_get(ck)
        if cached is not None:
            hit_elapsed = round((time.monotonic() - t_start) * 1000, 1)
            result = dict(cached)
            result["meta"] = dict(cached["meta"])
            result["meta"]["cache_hit"] = True
            result["meta"]["latency_ms"] = hit_elapsed
            return result
        data = _get_all_topics_articles(resolved_date)
        items = normalize_raw(data)
        elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)
        response = {
            "topic":     ALL_TOPIC_NAME,
            "mode_used": "raw",
            "available": bool(items),
            "items":     items,
            "meta": {
                "requested_topic": topic,
                "resolved_date":   resolved_date.isoformat(),
                "mode_used":       "raw",
                "items_count":     len(items),
                "latency_ms":      elapsed_ms,
                "cache_hit":       False,
            },
        }
        if items:
            _cache_set(ck, response)
        return response

    # 1. Resolve the report date (cheap DB MAX query)
    resolved_date, date_fallback = _resolve_report_date(topic, report_date)

    # 2. Select the preferred mode (pure CPU, no I/O)
    mode_selected, mode_reason = _select_mode(topic, user_agent, client_type)

    # 3. Cache lookup — key is stable after steps 1 and 2
    ck = _cache_key(topic, resolved_date, mode_selected)
    cached = _cache_get(ck)
    if cached is not None:
        hit_elapsed = round((time.monotonic() - t_start) * 1000, 1)
        _log(
            "auto_feed_cache_hit",
            topic=topic,
            mode_selected=mode_selected,
            resolved_date=resolved_date,
            latency_ms=hit_elapsed,
        )
        result = dict(cached)
        result["meta"] = dict(cached["meta"])
        result["meta"]["cache_hit"] = True
        result["meta"]["latency_ms"] = hit_elapsed
        return result

    # 4. Walk the fallback chain until we get items
    chain = _build_fallback_chain(mode_selected)
    items: list[dict] = []
    data: dict = {}
    mode_used = mode_selected
    fallback_applied = False
    fallback_reason: str | None = None

    for candidate in chain:
        try:
            candidate_items, candidate_data = _load_for_mode(candidate, topic, resolved_date)
        except Exception as exc:
            _log(
                "feed_mode_error",
                mode=candidate,
                topic=topic,
                error=str(exc)[:120],
            )
            candidate_items, candidate_data = [], {}

        if candidate_items:
            items = candidate_items
            data = candidate_data
            mode_used = candidate
            if candidate != mode_selected:
                fallback_applied = True
                fallback_reason = "selected_mode_returned_zero_items"
            break

    elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)

    _log(
        "auto_feed_served",
        topic=topic,
        mode_selected=mode_selected,
        mode_used=mode_used,
        fallback=fallback_applied,
        date_fallback=date_fallback,
        resolved_date=resolved_date,
        items=len(items),
        latency_ms=elapsed_ms,
    )

    response = {
        "topic":     data.get("topic", topic),
        "mode_used": mode_used,
        "available": bool(items),
        "items":     items,
        "meta": {
            "requested_topic":       topic,
            "resolved_topic":        data.get("topic", topic),
            "requested_date":        report_date.isoformat() if report_date else None,
            "resolved_date":         resolved_date.isoformat(),
            "date_fallback_applied": date_fallback,
            "mode_selected":         mode_selected,
            "mode_used":             mode_used,
            "mode_reason":           mode_reason,
            "fallback_applied":      fallback_applied,
            "fallback_reason":       fallback_reason,
            "fallback_chain":        chain,
            "items_count":           len(items),
            "latency_ms":            elapsed_ms,
            "cache_hit":             False,
            "cache_ttl_seconds":     _CACHE_TTL,
        },
    }

    # Cache non-empty results only
    if items:
        _cache_set(ck, response)

    return response
