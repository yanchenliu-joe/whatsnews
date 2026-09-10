"""
RSS fetching (Phase 7.2B, concurrent fetch + timeout in Phase 15.1).

Fetches a single feed and returns a list of standardized article dicts.
No database access — pure fetch + normalize.  This is the building block the
ingestion service will use; it does not write anything itself.

Standalone test (prints the first 3 normalized articles from a feed):
    python -m app.ingestion.rss
    python -m app.ingestion.rss "https://www.carbonbrief.org/feed/"
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import feedparser
import httpx

from app.ingestion.config import get_ingestion_feed_timeout_seconds
from app.ingestion.normalize import normalize_rss_entry

_USER_AGENT = "WhatsNews/0.1"


def _log(event: str, **kwargs) -> None:
    """Structured log line, matching the rest of the codebase's _log() style."""
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


@dataclass(frozen=True)
class FeedFetchResult:
    """Structured RSS fetch outcome for ingestion timing and error isolation."""

    articles: list[dict]
    status: str  # ok | timeout | error
    error: str | None = None
    duration_seconds: float = 0.0


def _parse_feed_entries(
    feed: feedparser.FeedParserDict,
    feed_url: str,
    max_items: int | None,
) -> list[dict]:
    feed_meta = getattr(feed, "feed", {}) or {}
    feed_source = ""
    if isinstance(feed_meta, dict):
        feed_source = (feed_meta.get("title") or "").strip()

    articles: list[dict] = []
    for entry in feed.entries:
        try:
            article = normalize_rss_entry(entry, source=feed_source)
            if not article["title"] or not article["url"]:
                continue
            articles.append(article)
        except Exception as e:
            _log("rss_normalize_error", url=feed_url, error=str(e)[:200])
            continue

    if max_items is not None and max_items > 0:
        articles = articles[:max_items]
    return articles


def fetch_rss_feed_result(
    feed_url: str,
    max_items: int | None = None,
    timeout_seconds: float | None = None,
) -> FeedFetchResult:
    """
    Fetch and parse an RSS feed with an HTTP timeout.

    Returns a FeedFetchResult (never raises).  On network/parse failure,
    articles is empty and status/error describe the failure.
    """
    started = time.monotonic()
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else get_ingestion_feed_timeout_seconds()
    )

    try:
        with httpx.Client(
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = client.get(feed_url)
            response.raise_for_status()
            content = response.content
    except httpx.TimeoutException:
        duration = round(time.monotonic() - started, 2)
        message = f"Feed fetch timed out after {timeout}s"
        _log("rss_fetch_timeout", url=feed_url, seconds=duration)
        return FeedFetchResult([], "timeout", message, duration)
    except Exception as e:
        duration = round(time.monotonic() - started, 2)
        message = str(e)[:200]
        _log("rss_fetch_error", url=feed_url, error=message)
        return FeedFetchResult([], "error", message, duration)

    try:
        feed = feedparser.parse(content)
    except Exception as e:
        duration = round(time.monotonic() - started, 2)
        message = str(e)[:200]
        _log("rss_parse_error", url=feed_url, error=message)
        return FeedFetchResult([], "error", message, duration)

    if feed.bozo and not feed.entries:
        duration = round(time.monotonic() - started, 2)
        message = str(getattr(feed, "bozo_exception", "feed parse error"))[:200]
        _log("rss_parse_error", url=feed_url, error=message)
        return FeedFetchResult([], "error", message, duration)

    articles = _parse_feed_entries(feed, feed_url, max_items)
    duration = round(time.monotonic() - started, 2)
    _log("rss_fetch_done", url=feed_url, count=len(articles), seconds=duration)
    return FeedFetchResult(articles, "ok", None, duration)


def fetch_rss_feed(feed_url: str, max_items: int | None = None) -> list[dict]:
    """
    Fetch and parse an RSS feed, returning a list of standardized article dicts:
      [{ "title", "summary", "url", "published_at", "source" }, ...]

    - Returns [] on any fetch/parse failure (never raises).
    - Skips individual entries missing a title or url.
    - Fills `source` from the feed title when an entry doesn't carry its own.
    - When max_items is set, returns at most that many entries (after parsing).
    """
    return fetch_rss_feed_result(feed_url, max_items=max_items).articles


# ── Standalone test helper ────────────────────────────────────────────────────

def _demo(feed_url: str) -> None:
    """Fetch one feed and pretty-print the first 3 normalized articles."""
    result = fetch_rss_feed_result(feed_url)
    articles = result.articles
    print(f"\nFetched {len(articles)} article(s) from: {feed_url}")
    print(f"status={result.status} duration={result.duration_seconds}s")
    if result.error:
        print(f"error={result.error}")
    print()
    for i, article in enumerate(articles[:3], start=1):
        published = article["published_at"]
        published_str = published.isoformat() if published else "None"
        print(f"--- Article {i} ---")
        print(f"  title:        {article['title']}")
        print(f"  source:       {article['source']}")
        print(f"  url:          {article['url']}")
        print(f"  published_at: {published_str}")
        print(f"  summary:      {article['summary'][:160]}")
        print()


if __name__ == "__main__":
    import sys

    default_feed = "https://www.carbonbrief.org/feed/"
    url = sys.argv[1] if len(sys.argv) > 1 else default_feed
    _demo(url)
