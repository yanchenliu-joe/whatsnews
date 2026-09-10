"""Ingestion tuning via environment variables (Phase 15.1)."""

import os

_DEFAULT_MAX_CONCURRENCY = 20  # Raised from 8 (2026-07-06 speed pass) — pure I/O
# fan-out over ~300 distinct feed hosts; does not change which feeds are
# fetched or how articles are filtered/selected.
_DEFAULT_FEED_TIMEOUT_SECONDS = 10
_DEFAULT_SLOW_SOURCE_THRESHOLD_SECONDS = 5


def get_ingestion_max_concurrency() -> int:
    raw = os.getenv("INGESTION_MAX_CONCURRENCY", str(_DEFAULT_MAX_CONCURRENCY))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_CONCURRENCY


def get_ingestion_feed_timeout_seconds() -> float:
    raw = os.getenv("INGESTION_FEED_TIMEOUT_SECONDS", str(_DEFAULT_FEED_TIMEOUT_SECONDS))
    try:
        return max(1.0, float(raw))
    except ValueError:
        return float(_DEFAULT_FEED_TIMEOUT_SECONDS)


def get_ingestion_slow_source_threshold_seconds() -> float:
    raw = os.getenv(
        "INGESTION_SLOW_SOURCE_THRESHOLD_SECONDS",
        str(_DEFAULT_SLOW_SOURCE_THRESHOLD_SECONDS),
    )
    try:
        return max(0.0, float(raw))
    except ValueError:
        return float(_DEFAULT_SLOW_SOURCE_THRESHOLD_SECONDS)


def get_ingestion_topic_concurrency() -> int:
    """Parallel topic DB persist workers during a full ingestion pass."""
    raw = os.getenv("INGESTION_TOPIC_CONCURRENCY")
    if raw is None:
        return min(4, get_ingestion_max_concurrency())
    try:
        return max(1, int(raw))
    except ValueError:
        return min(4, get_ingestion_max_concurrency())


def get_ingestion_db_batch_size() -> int:
    raw = os.getenv("INGESTION_DB_BATCH_SIZE", "100")
    try:
        return max(1, int(raw))
    except ValueError:
        return 100


def article_scraping_enabled() -> bool:
    """Whether to fetch full article body text during ingestion (opt-in)."""
    return os.getenv("ENABLE_ARTICLE_SCRAPING", "false").lower() in ("true", "1", "yes")


_DEFAULT_SCRAPE_CONCURRENCY = 8  # Raised from a hardcoded 4 (2026-07-09 speed
# pass). Runs per-topic, and up to get_ingestion_topic_concurrency() topics
# run at once, so worst-case total concurrent scrape requests is topic
# concurrency x this value — kept moderate (not raised as far as the plain
# RSS-fetch concurrency) since scraping downloads full HTML pages and runs
# CPU-bound extraction, unlike small RSS XML fetches. Combines with the
# same-pass fix that scrapes only genuinely-new articles (post-dedup), not
# every record missing body_text.


def get_scrape_concurrency() -> int:
    raw = os.getenv("INGESTION_SCRAPE_CONCURRENCY", str(_DEFAULT_SCRAPE_CONCURRENCY))
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_SCRAPE_CONCURRENCY
