"""
Fetch og:image / twitter:image from article URLs for articles missing image_url.
Uses a sync ThreadPoolExecutor so it can be called safely from the sync pipeline.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

import httpx

from app.database import get_connection

_TIMEOUT = 5.0
_MAX_WORKERS = 20  # Raised from 10 (2026-07-06 speed pass) — pure I/O fan-out
# over up to 200 distinct article-source hosts; doesn't change which
# articles are checked or what counts as a valid og:image.
_HEAD_READ_BYTES = 32_768  # parse first 32 KB only — og:image is always in <head>
_USER_AGENT = "Mozilla/5.0 (compatible; WhatsNewsBot/1.0)"


# ── HTML parser ───────────────────────────────────────────────────────────────

class _OGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta" or self.image:
            return
        d = {k: (v or "") for k, v in attrs}
        prop = (d.get("property") or d.get("name") or "").lower()
        if prop in ("og:image", "og:image:url", "twitter:image", "twitter:image:src"):
            val = d.get("content", "").strip()
            if val.startswith("http"):
                self.image = val


def _parse_og_image(html: str) -> str | None:
    parser = _OGParser()
    head_end = html.find("</head>")
    parser.feed(html[:head_end] if head_end > 0 else html[:_HEAD_READ_BYTES])
    return parser.image


# ── Per-URL fetch ─────────────────────────────────────────────────────────────

def _fetch_og_image(url: str) -> str | None:
    """
    Streams the response and stops after _HEAD_READ_BYTES instead of
    downloading the full page first — og:image is always in <head>, so the
    rest of the page (often several MB of scripts/images/tracking pixels)
    was previously downloaded into memory just to be thrown away. Found
    2026-07-07 while tracking down OOM crashes on Render's Starter plan
    (512MB) during a full 20-topic pipeline run with high concurrency.
    """
    try:
        with httpx.Client(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return None
                chunks = []
                downloaded = 0
                for chunk in resp.iter_bytes():
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if downloaded >= _HEAD_READ_BYTES:
                        break
                raw = b"".join(chunks)
            return _parse_og_image(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


# ── Main entry ────────────────────────────────────────────────────────────────

def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def fill_missing_og_images() -> dict:
    """
    Query articles that are in a report but have no image_url, fetch og:image
    concurrently, and persist results. Safe to call from the sync pipeline.
    """
    started = time.perf_counter()
    try:
        conn = get_connection()
        cur = conn.cursor()
    except Exception as e:
        _log("og_image_fill_db_error", error=str(e)[:200])
        return {"error": str(e)[:200]}

    try:
        cur.execute(
            """
            SELECT id, url FROM articles
            WHERE report_id IS NOT NULL
              AND image_url IS NULL
              AND url IS NOT NULL
              AND published_at > NOW() - INTERVAL '14 days'
            ORDER BY id DESC
            LIMIT 200
            """
        )
        rows = cur.fetchall()
        if not rows:
            _log("og_image_fill_skip", reason="no_articles_missing_images")
            return {"articles_checked": 0, "fetched": 0, "updated": 0}

        _log("og_image_fill_start", articles=len(rows))

        # Concurrent OG image fetch
        url_map: dict[str, int] = {row["url"]: row["id"] for row in rows}
        fetch_results: dict[int, str | None] = {}

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_og_image, url): url for url in url_map}
            for future in as_completed(futures):
                url = futures[future]
                article_id = url_map[url]
                try:
                    fetch_results[article_id] = future.result()
                except Exception:
                    fetch_results[article_id] = None

        # Persist
        updated = 0
        for article_id, image_url in fetch_results.items():
            if image_url:
                cur.execute(
                    "UPDATE articles SET image_url = %s WHERE id = %s AND image_url IS NULL",
                    (image_url, article_id),
                )
                updated += cur.rowcount

        conn.commit()

        fetched = sum(1 for img in fetch_results.values() if img)
        elapsed = round(time.perf_counter() - started, 2)
        _log(
            "og_image_fill_done",
            articles=len(rows),
            fetched=fetched,
            updated=updated,
            elapsed=elapsed,
        )
        return {
            "articles_checked": len(rows),
            "fetched": fetched,
            "updated": updated,
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        _log("og_image_fill_error", error=str(e)[:300])
        try:
            conn.rollback()
        except Exception:
            pass
        return {"error": str(e)[:300]}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
