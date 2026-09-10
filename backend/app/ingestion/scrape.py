"""
Article body text scraping using httpx + trafilatura.

Fetches the article URL with a real browser User-Agent and extracts the main
content (boilerplate/nav/ads removed).  Called during ingestion after RSS
normalization, gated by ENABLE_ARTICLE_SCRAPING=true.
"""

from __future__ import annotations

import concurrent.futures
import re
import time

import httpx
import trafilatura

_SCRAPE_TIMEOUT_SECONDS = 10
_MAX_BODY_CHARS = 8000
_MIN_BODY_CHARS = 150  # ignore pages that return almost nothing (404, JS gates)
# Streamed and capped rather than downloading the full page — some sites
# serve several MB of scripts/images/tracking payloads per article, all
# discarded after extracting <= _MAX_BODY_CHARS of text anyway. Found
# 2026-07-07 while tracking down OOM crashes on Render's Starter plan
# (512MB) during a full 20-topic pipeline run with high concurrency; article
# text on well-structured news pages is essentially always within this cap.
_MAX_DOWNLOAD_BYTES = 1_500_000

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# A leading stray short line (e.g. a photo-gallery counter like "2" that
# trafilatura sometimes captures ahead of the real first paragraph).
_RE_LEADING_JUNK_LINE = re.compile(r"^\s*[\d.\-–—]{1,4}\s*\n+")

# A leading photo caption + credit line, e.g. "In this pool photograph
# distributed by ... | POOL/AFP via Getty Images" — trafilatura sometimes
# includes the image caption block ahead of the real article body on sites
# that mark it up close to the main content (confirmed on Vox.com, 2026-07-09).
# Anchored to a "|"-separated credit segment containing a known photo-agency
# keyword, matched only near the start of the text (captions are always the
# first thing, never buried mid-article) to avoid stripping a legitimate
# "According to Reuters, ..." sentence later in real prose.
_PHOTO_CREDIT_AGENCIES = (
    r"Getty Images|Getty|AFP|AP Photo|AP|Reuters|EPA|Bloomberg|Shutterstock|"
    r"WireImage|Zuma Press|ZUMA|POOL|Pool"
)
_RE_LEADING_PHOTO_CREDIT = re.compile(
    r"^.{0,400}?\|\s*(?:[\w./\-]+\s*)?(?:via\s+)?"
    rf"(?:{_PHOTO_CREDIT_AGENCIES})\b[.,;:]?",
    re.IGNORECASE,
)

# Trailing boilerplate markers — related-content/newsletter/disclosure
# footers that some sites append after the real article. Found 2026-07-10 by
# frequency-analyzing which exact lines repeat verbatim across many
# different articles (real prose is essentially never duplicated across
# unrelated articles; site boilerplate is). Position-checked against every
# matching row in production before adding: each of these sits consistently
# in the last ~10-20% of the text (median 80-99%, e.g. "More on the subject"
# median 99%, "Get the TNW newsletter" median 97%) — safe to truncate
# everything from the first occurrence onward. Deliberately NOT included:
# "Popular on Variety"/"Watch on Deadline"/"More News from Barchart"/
# "Recommended Stories" — these showed up anywhere from 8% to 96% into the
# text (embedded mid-article widgets, not trailing footers), so truncating
# at them would delete real trailing content as often as it would remove
# junk. Left alone rather than guessing.
_TRAILING_BOILERPLATE_MARKERS = (
    "--Field Level Media",
    "More on the subject",
    "Get the TNW newsletter",
    "READ NEXT:",
    "Disclosure: None. Follow Insider Monkey on Google News.",
    "Worth checking out on Amazon",
    "More Top Reads From Oilprice.com",
)

# Mid-article "related content" widget headings (Technical Debt #23,
# resolved 2026-07-13) — "Popular on Variety" / "Watch on Deadline" /
# "More News from Barchart" showed up anywhere from 8% to 96% into the
# text, which is why they were left alone when the trailing-footer
# markers above were added: a widget embedded mid-article looked like it
# would need real start/end boundary detection, not a truncate-from-here.
# Sampling ~300 real rows from the live DB found the opposite: trafilatura
# already strips the widget's own link items (they're presumably marked
# up as a nav/aside block it correctly filters) — only the bare heading
# text bleeds through, sitting inline between two real paragraphs with no
# actual list content on either side. So the fix is a straight substring
# removal, not a truncation; real content on both sides is preserved.
_RE_RELATED_WIDGET_HEADING = re.compile(
    r"(?:Popular on Variety|Watch on Deadline|More News from Barchart)\n?"
)

# Al Jazeera's "Recommended Stories" widget DOES have real list content
# (unlike the three above) but with a fully determinate, parseable
# structure: "Recommended Stories\nlist of N items" followed by exactly N
# "- list K of N<title>" entries, then the real article resumes with no
# other marker. Confirmed against all 159 real matching rows in the live
# DB — 157 parsed cleanly this way; the remaining 2 use a different
# singular-item format ("list of 1 itemend of list", no entries at all),
# handled separately below.
_RE_AL_JAZEERA_RECOMMENDED_HEADER = re.compile(r"Recommended Stories\nlist of (\d+) items")
_AL_JAZEERA_SINGULAR_ITEM = "Recommended Stories\nlist of 1 itemend of list"

# ZDNET's "Why you can trust ZDNET" editorial-process disclosure always
# leads the scraped text (confirmed at index 0 across every matching row),
# with the real article starting immediately after a consistent closing
# sentence. Byte-identical boilerplate template across articles, unlike the
# generic photo-credit case above, so matched as literal strings rather than
# a keyword pattern.
_ZDNET_DISCLOSURE_START = "Why you can trust ZDNET"
_ZDNET_DISCLOSURE_END_MARKER = "please report the mistake via this form."

# Nav/menu dumps trafilatura occasionally falls back to on pages where it
# can't confidently identify the main content block: many short lines
# (site name, section links, "Advertising", "go to home", etc.) with no
# sentence-ending punctuation.
_NAV_DUMP_MAX_WORDS_PER_LINE = 5
_NAV_DUMP_LINE_RATIO_THRESHOLD = 0.6
_NAV_DUMP_MIN_LINES = 6


def _strip_leading_junk_line(text: str) -> str:
    return _RE_LEADING_JUNK_LINE.sub("", text, count=1)


def _strip_leading_photo_credit(text: str) -> str:
    return _RE_LEADING_PHOTO_CREDIT.sub("", text, count=1)


def _truncate_at_trailing_boilerplate(text: str) -> str:
    earliest_idx = None
    for marker in _TRAILING_BOILERPLATE_MARKERS:
        idx = text.find(marker)
        if idx >= 0 and (earliest_idx is None or idx < earliest_idx):
            earliest_idx = idx
    if earliest_idx is None:
        return text
    return text[:earliest_idx].rstrip()


def _strip_related_widget_headings(text: str) -> str:
    return _RE_RELATED_WIDGET_HEADING.sub("", text)


def _strip_al_jazeera_recommended_stories(text: str) -> str:
    text = text.replace(_AL_JAZEERA_SINGULAR_ITEM, "")

    match = _RE_AL_JAZEERA_RECOMMENDED_HEADER.search(text)
    if not match:
        return text

    count = int(match.group(1))
    start = match.start()
    pos = match.end()
    for _ in range(count):
        entry_match = re.match(rf"- list \d+ of {count}[^\n]*\n?", text[pos:])
        if not entry_match:
            # Doesn't match the expected N-entry structure — bail out
            # rather than guess at a boundary; leave the text untouched.
            return text
        pos += entry_match.end()
    return text[:start] + text[pos:]


def _strip_zdnet_leading_disclosure(text: str) -> str:
    if not text.startswith(_ZDNET_DISCLOSURE_START):
        return text
    end_idx = text.find(_ZDNET_DISCLOSURE_END_MARKER)
    if end_idx == -1:
        return text
    return text[end_idx + len(_ZDNET_DISCLOSURE_END_MARKER):].lstrip()


def _looks_like_navigation_dump(text: str) -> bool:
    """
    Heuristic: real article prose is mostly full sentences; a nav/menu dump
    is mostly short link-label lines with no terminal punctuation. Used to
    reject a "successful" extraction that actually just grabbed boilerplate.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < _NAV_DUMP_MIN_LINES:
        return False
    short_no_punct = sum(
        1
        for ln in lines
        if len(ln.split()) <= _NAV_DUMP_MAX_WORDS_PER_LINE
        and not ln.rstrip().endswith((".", "!", "?", "…", '"', "'", "”"))
    )
    return (short_no_punct / len(lines)) >= _NAV_DUMP_LINE_RATIO_THRESHOLD


def _fetch_body(url: str) -> str:
    """Blocking fetch + extract. Runs inside a thread pool."""
    try:
        with httpx.stream(
            "GET",
            url,
            headers=_HEADERS,
            follow_redirects=True,
            timeout=_SCRAPE_TIMEOUT_SECONDS,
        ) as response:
            if response.status_code != 200:
                return ""
            chunks = []
            downloaded = 0
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                downloaded += len(chunk)
                if downloaded >= _MAX_DOWNLOAD_BYTES:
                    break
            html = b"".join(chunks).decode("utf-8", errors="replace")

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
        )
        if not text:
            return ""

        text = _strip_zdnet_leading_disclosure(text)
        text = _strip_leading_photo_credit(text)
        text = _strip_leading_junk_line(text).strip()
        text = _strip_al_jazeera_recommended_stories(text)
        text = _strip_related_widget_headings(text)
        text = _truncate_at_trailing_boilerplate(text).strip()
        if len(text) < _MIN_BODY_CHARS or _looks_like_navigation_dump(text):
            return ""

        return text[:_MAX_BODY_CHARS]
    except Exception:
        return ""


def scrape_body_texts_concurrent(
    articles: list[dict],
    *,
    max_workers: int = 4,
) -> dict[str, str]:
    """
    Scrape body text for multiple articles concurrently.

    Takes a list of article dicts with a 'url' key.
    Returns a {url: body_text} mapping for articles that yielded content.
    Articles that fail or time out are omitted.
    """
    urls = [a.get("url", "") for a in articles if a.get("url")]
    if not urls:
        return {}

    results: dict[str, str] = {}
    wall_timeout = _SCRAPE_TIMEOUT_SECONDS * 2 + 5  # generous wall clock cap

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_url = {pool.submit(_fetch_body, url): url for url in urls}
        try:
            for future in concurrent.futures.as_completed(
                future_to_url, timeout=wall_timeout
            ):
                url = future_to_url[future]
                try:
                    text = future.result(timeout=1)
                    if text:
                        results[url] = text
                except Exception:
                    pass
        except concurrent.futures.TimeoutError:
            pass

    return results
