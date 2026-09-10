"""
RSS entry normalization (Phase 7.2B).

Pure functions that convert a raw feedparser entry into a standardized article
dict.  No database access, no network access — easy to unit test.
"""

import html
import re
from calendar import timegm
from datetime import datetime
from zoneinfo import ZoneInfo

_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_PARAGRAPH_BREAK = re.compile(r"[ \t]*\n[ \t]*(?:\n[ \t]*)*")
_FALLBACK_DATE_FORMATS = (
    "%b %d, %Y %I:%M%p",   # Jun 22, 2026 4:51pm (Fierce Healthcare)
    "%b %d, %Y %I:%M %p",  # spaced am/pm variant
)

# Truncation artifacts many source feeds embed in excerpt-only summary/content
# fields (teaser text cut short by the publisher, not by WhatsNews). Stripped
# from summary/body_text only — never from titles.
_RE_BRACKET_ELLIPSIS = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]")
_RE_WORDPRESS_EXCERPT_FOOTER = re.compile(
    r"\s*The post .+? appeared first on .+?\.\s*$", re.IGNORECASE
)
_RE_CONTINUE_READING = re.compile(
    r"\s*(?:continue reading|read more)\s*\.{0,3}\s*$", re.IGNORECASE
)
_RE_TRAILING_ELLIPSIS = re.compile(r"[.…]{3,}\s*$")

# Boilerplate found embedded in RSS full-content/scraped body text (2026-07-13)
# — reads fine as prose on the source's own page (surrounded by real nav/ads/
# widgets there), but looks like stray junk once extracted as a standalone
# summary shown out of context in this app. Each pattern below was found from
# a real sample of generated summaries, not guessed — see improve_short_summaries.py.
_RE_COPYRIGHT_FOOTER = re.compile(
    r"\s*Copyright\s*©.*$", re.IGNORECASE | re.DOTALL
)
_RE_HYPEBEAST_GALLERY_CTA = re.compile(
    r"\s*Click here to view full gallery at [^.]*\.?\s*$", re.IGNORECASE
)
_RE_GENERIC_CLICK_HERE = re.compile(
    r"\s*Click here[^.!?]*[.!?]", re.IGNORECASE
)
_RE_SIGNUP_CTA = re.compile(
    r"\s*Sign up here to get notified[^.!?]*[.!?]", re.IGNORECASE
)
_RE_MIT_NEWSLETTER_INTRO = re.compile(
    r"^This is today.s edition of .+?, our (?:daily|weekday) newsletter that "
    r"provides a daily dose of what.s going on in the world of [^.]*\.\s*",
    re.IGNORECASE,
)
_RE_CNET_PUZZLE_INTRO = re.compile(
    r"^Looking for the most recent .+? answer\? Click here for our daily "
    r".+?puzzles?\.\s*",
    re.IGNORECASE,
)
# IndieWire/Penske Media network's fixed GDPR-consent + reCAPTCHA disclaimer,
# always the very first thing in the body — identical wording across every
# article sampled, safe as a literal leading-string match rather than a
# looser pattern.
_RE_INDIEWIRE_CONSENT_DISCLAIMER = re.compile(
    r"^By providing your information, you agree to our Terms of Use and our "
    r"Privacy Policy\. We use vendors that may also process your information "
    r"to help provide our services\. This site is protected by reCAPTCHA "
    r"Enterprise and the Google Privacy Policy and Terms of Service apply\.\s*",
    re.IGNORECASE,
)
# "This post originally appeared in the X newsletter." + the matching
# "sign up ... here" follow-up sentence (Business Insider's newsletter-
# reprint boilerplate) — two separate sentences, stripped independently.
_RE_ORIGINALLY_APPEARED_NEWSLETTER = re.compile(
    r"\s*This post originally appeared in the .+? newsletter\.\s*", re.IGNORECASE
)
_RE_SIGNUP_FOR_NEWSLETTER = re.compile(
    r"\s*You can sign up for .+? newsletter (?:here|in your inbox)[^.!?]*[.!?]",
    re.IGNORECASE,
)
# "(This is the X newsletter, ...)" parenthetical intro (CNBC's Buffett Watch
# and similar syndicated-newsletter articles) — non-greedy up to the closing
# paren so it can't swallow unrelated later content.
_RE_PARENTHETICAL_NEWSLETTER_INTRO = re.compile(
    r"\s*\(This is the .+? newsletter,.*?\)\s*", re.IGNORECASE
)
# "Subscribe to X [Podcast] on YouTube/Apple Podcasts/Spotify[, ...]."
# (podcast-promo CTA seen mid-article on lifestyle/culture sites).
_RE_SUBSCRIBE_PODCAST_CTA = re.compile(
    r"\s*Subscribe to .+? on (?:YouTube|Apple Podcasts|Spotify)[^.!?]*[.!?]",
    re.IGNORECASE,
)
# "This is an edition of the newsletter X, ...'s weekly/daily deep dive
# into ... Sign up here." (GQ-style newsletter-reprint intro).
_RE_EDITION_OF_NEWSLETTER = re.compile(
    r"\s*This is an edition of the newsletter .+?\. Sign up here\.\s*",
    re.IGNORECASE,
)
# "This story was originally published on X. To receive ... insights,
# subscribe to our ... newsletter." (Yahoo Finance/Grocery Dive syndication
# boilerplate) — two sentences, stripped independently like Business
# Insider's variant above.
_RE_ORIGINALLY_PUBLISHED_ON = re.compile(
    r"\s*This story was originally published on [^.]*\.\s*", re.IGNORECASE
)
_RE_SUBSCRIBE_TO_RECEIVE = re.compile(
    r"\s*To receive [^,]*, subscribe to (?:our|their) [^.!?]*[.!?]", re.IGNORECASE
)
# "Welcome to our X newsletter[,.]" (CoinDesk and similar syndicated crypto/
# finance newsletters) — bounded at the first comma/period so it can't run on.
_RE_WELCOME_TO_NEWSLETTER = re.compile(
    r"\s*Welcome to our [^,.]* newsletter[,.]\s*", re.IGNORECASE
)
# More newsletter-reprint intro variants (2026-07-13, second sample pass) —
# each paired with its own specific subscribe/signup CTA sentence so the
# CTA half stays narrow enough to not risk stripping legitimate content
# that happens to mention "sign up" (e.g. an article describing how to
# join an unrelated membership program).
_RE_VERSION_OF_ARTICLE_NEWSLETTER = re.compile(
    r"\s*A version of this article (?:first|originally) appeared in .+? "
    r"newsletter(?:, which [^.!?]*)?[.!?]\s*",
    re.IGNORECASE,
)
_RE_STORY_RAN_IN_NEWSLETTER = re.compile(
    r"\s*This story originally ran in the newsletter [^.!?]*[.!?]\s*", re.IGNORECASE
)
_RE_ARTICLE_VERSION_OF_NEWSLETTER = re.compile(
    r"\s*This is an article version of the .+? [Nn]ewsletter(?:, [^.!?]*)?[.!?]\s*",
    re.IGNORECASE,
)
_RE_NEWSLETTER_CTA_FOLLOWUP = re.compile(
    r"\s*(?:Subscribe here to receive[^.!?]*|Sign up here to (?:get|receive)[^.!?]*|"
    r"You can sign up to get it[^.!?]*)[.!?]\s*",
    re.IGNORECASE,
)
_RE_NEWSLETTER_WRITTEN_BY_DISCLAIMER = re.compile(
    r"\s*[^.!?]*? is a daily newsletter written by [^.!?]*[.!?]\s*"
    r"The analysis and opinions expressed are (?:his|her|their) own and do "
    r"not necessarily reflect those of [^.!?]*[.!?]\s*",
    re.IGNORECASE,
)
_RE_NEWSLETTER_SECTION_HEADER = re.compile(
    r"\s*The \w+ Newsletter Weekly insights and analysis on [^.!?]*[.!?]\s*",
    re.IGNORECASE,
)
_RE_PUBLISHED_BY_SIGNUP_NEWSLETTERS = re.compile(
    r"\s*This story was originally published by [^.!?]*[.!?]\s*"
    r"Sign up for their newsletters?\.?\s*",
    re.IGNORECASE,
)
# Generic structural fallback (2026-07-13) for the many differently-worded
# newsletter-reprint intros found across sources (CNBC, Quartz, IndieWire,
# CBS Sports, GQ, Vox, CoinDesk, Canary Media, Business Insider, ...) —
# rather than chase every publisher's exact phrasing with its own regex
# forever, this targets the shared *structure*: a first sentence that both
# (a) OPENS with a self-referential phrase ("This story/article/post/is/
# analysis...", "A version of this...", "Welcome to our...", "In this
# week's/day's...") and (b) mentions "newsletter" somewhere in that same
# sentence. Anchoring the self-reference to the START of the sentence
# (rather than a loose proximity search) matters: an earlier, looser
# version of this matched "...for young readers this week." in a genuine
# third-party news story about a newsletter launch, since "this" appeared
# merely somewhere near "newsletter" — requiring it to open the sentence
# avoids that false positive while still catching every real intro
# variant sampled (each one opens this way).
_RE_FIRST_SENTENCE = re.compile(r"^\s*([^.!?]*[.!?])\s*")
_RE_SELF_REFERENTIAL_OPENING = re.compile(
    r"^(?:This\b|A version of this\b|Welcome to (?:our|my)\b|In this (?:week|day)'?s\b)",
    re.IGNORECASE,
)
_RE_SIGNUP_OR_SUBSCRIBE = re.compile(r"sign up|subscribe", re.IGNORECASE)


def _strip_generic_newsletter_intro(text: str) -> str:
    first = _RE_FIRST_SENTENCE.match(text)
    if not first:
        return text
    sentence = first.group(1)
    if "newsletter" not in sentence.lower() or not _RE_SELF_REFERENTIAL_OPENING.match(sentence):
        return text
    remainder = text[first.end():]
    cta = _RE_FIRST_SENTENCE.match(remainder)
    if cta and _RE_SIGNUP_OR_SUBSCRIBE.search(cta.group(1)):
        remainder = remainder[cta.end():]
    return remainder.lstrip()
# A source's own auto-generated "Summary" bullet block glued to the front of
# body_text with no separating space (e.g. Hypebeast) — identifiable only by
# the literal leading word "Summary" run directly into a capitalized word.
_RE_LEADING_SUMMARY_LABEL = re.compile(r"^Summary(?=[A-Z])")
# Sentences that lost their separating space somewhere upstream (e.g.
# "acoustics.Features include" — seen in Hypebeast's scraped bullet blocks).
_RE_GLUED_SENTENCE = re.compile(r"([.!?])(?=[A-Z])")
# Open-ended CTAs with no clean closing boundary (e.g. NME's
# "READ MORE: <related article title>" runs directly into the next
# sentence with no punctuation marking where the title ends) — can't be
# safely stripped out of the middle without risking eating real content, so
# _strip_body_boilerplate() truncates everything from the first occurrence
# onward instead (a hard stop, same as truncate-at-trailing-boilerplate
# logic elsewhere): the summary just never extends past it, even if that
# means ending up shorter than usual.
_RE_HARD_STOP_MARKERS = re.compile(r"READ MORE:", re.IGNORECASE)


def _strip_body_boilerplate(text: str) -> str:
    """
    Remove known site-boilerplate patterns from body_text (or an
    already-assembled summary) before it's shown to users — trailing
    footers (copyright lines, "click here to view full gallery" CTAs),
    leading template intros (MIT Tech Review's "Download" newsletter,
    CNET's daily-puzzle-hints preamble, IndieWire's consent disclaimer, a
    glued-on "Summary" auto-recap label), newsletter-reprint boilerplate
    (Business Insider/Grocery Dive/GQ/CoinDesk-style "this post originally
    appeared in/is an edition of/welcome to our ... newsletter" intros),
    and generic mid-text engagement CTAs ("Click here to...", "Sign up
    here to...", podcast subscribe prompts). Also fixes sentences that
    lost their separating space (a glued "word.Next" artifact) and
    defensively strips any leftover HTML tags/entities, since this
    function runs on already-stored rows too (via the backfill script),
    not only on freshly-normalized text. Distinct from
    _strip_truncation_artifacts (which removes markers the *publisher*
    uses to signal their own teaser was cut short) — these are boilerplate
    that was never truncation, just noise that doesn't belong in a summary.
    """
    if not text:
        return text
    stop_match = _RE_HARD_STOP_MARKERS.search(text)
    if stop_match:
        text = text[: stop_match.start()]
    text = _RE_HTML_TAG.sub(" ", text)
    text = html.unescape(text)
    text = _RE_MIT_NEWSLETTER_INTRO.sub("", text)
    text = _RE_CNET_PUZZLE_INTRO.sub("", text)
    text = _RE_INDIEWIRE_CONSENT_DISCLAIMER.sub("", text)
    text = _RE_EDITION_OF_NEWSLETTER.sub("", text)
    text = _RE_ORIGINALLY_PUBLISHED_ON.sub("", text)
    text = _RE_SUBSCRIBE_TO_RECEIVE.sub("", text)
    text = _RE_WELCOME_TO_NEWSLETTER.sub("", text)
    text = _RE_VERSION_OF_ARTICLE_NEWSLETTER.sub("", text)
    text = _RE_STORY_RAN_IN_NEWSLETTER.sub("", text)
    text = _RE_ARTICLE_VERSION_OF_NEWSLETTER.sub("", text)
    text = _RE_NEWSLETTER_CTA_FOLLOWUP.sub("", text)
    text = _RE_NEWSLETTER_WRITTEN_BY_DISCLAIMER.sub("", text)
    text = _RE_NEWSLETTER_SECTION_HEADER.sub("", text)
    text = _RE_PUBLISHED_BY_SIGNUP_NEWSLETTERS.sub("", text)
    text = _strip_generic_newsletter_intro(text)
    text = _RE_LEADING_SUMMARY_LABEL.sub("", text)
    text = _RE_HYPEBEAST_GALLERY_CTA.sub("", text)
    text = _RE_COPYRIGHT_FOOTER.sub("", text)
    text = _RE_ORIGINALLY_APPEARED_NEWSLETTER.sub("", text)
    text = _RE_SIGNUP_FOR_NEWSLETTER.sub("", text)
    text = _RE_PARENTHETICAL_NEWSLETTER_INTRO.sub("", text)
    text = _RE_SUBSCRIBE_PODCAST_CTA.sub("", text)
    text = _RE_GENERIC_CLICK_HERE.sub("", text)
    text = _RE_SIGNUP_CTA.sub("", text)
    text = _RE_GLUED_SENTENCE.sub(r"\1 ", text)
    text = _collapse_whitespace_preserving_paragraphs(text)
    return text.strip()


def _collapse_whitespace_preserving_paragraphs(text: str) -> str:
    """
    Collapse whitespace like _clean_text's _RE_MULTI_SPACE, except any
    newline is preserved as exactly one "\\n" instead of being flattened
    to a plain space. Found 2026-07-13: an earlier version of
    _strip_body_boilerplate flattened every line break into a plain
    space, destroying formatting that ArticleDetailScreen.tsx's plain
    <Text> would otherwise render as real line breaks — actively working
    against the "clear layout, no wall of text" goal this whole pass is
    for. Checked directly against real stored body_text (2026-07-13):
    scrape.py's trafilatura call uses no `output_format` override, so it
    emits plain-text output with a *single* "\\n" between paragraphs and
    listicle items (confirmed against real BuzzFeed/ZDNET rows) — never
    "\\n\\n" — so a single newline is the real paragraph-break signal
    here, not incidental line-wrapping, and multiple consecutive
    newlines collapse down to just one rather than being preserved as an
    extra blank-line gap that was never actually in the source.
    """
    text = _RE_PARAGRAPH_BREAK.sub("\x00", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    return text.replace("\x00", "\n")


def _clean_text(text) -> str:
    """Strip HTML tags, decode entities, and collapse whitespace. Safe on None."""
    if not text:
        return ""
    text = _RE_HTML_TAG.sub(" ", str(text))
    text = html.unescape(text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


def truncate_at_word_boundary(text: str, limit: int) -> str:
    """
    Hard-cap `text` at `limit` characters without severing a word mid-way.
    Used where a column/field needs a defensive length ceiling (e.g.
    summary) — cuts at the last whitespace before the limit and appends a
    single "…" so a truncated field reads as intentional, not broken.
    Unlike _strip_truncation_artifacts (which removes truncation markers
    the *publisher* already added), this is WhatsNews' own truncation, so
    it always signals it clearly.
    """
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut.rstrip() + "…"


MIN_SUMMARY_LENGTH = 200
_SUMMARY_TARGET_LENGTH = 450
_SUMMARY_MAX_LENGTH = 650
_RE_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def extract_summary_from_body(
    body_text: str,
    min_length: int = _SUMMARY_TARGET_LENGTH,
    max_length: int = _SUMMARY_MAX_LENGTH,
) -> str:
    """
    Build a multi-sentence summary from `body_text` by extending to the
    first whole-sentence boundary at or past `min_length`, never exceeding
    `max_length`. Pure extraction, not rewriting — every character comes
    from `body_text` itself, so nothing is invented.

    Returns "" (rather than the raw text, at any length) when no
    sentence-ending punctuation appears *anywhere* in `body_text` — found
    2026-07-13 from a real NASA feed: navigation/menu-dump text ("Earth
    Observatory Earth Earth Observatory Image of the Day EO Explorer
    Topics...") has no periods at all, so it used to pass straight through
    as "already short enough" (or, before that, get word-boundary-
    truncated into a junk fragment). Real article text — even one long
    run-on lead sentence — essentially always has *a* sentence boundary
    somewhere; a total absence is a safe non-prose signal, and the caller
    (improve_summary_from_body) just keeps the existing summary instead.
    If a sentence boundary exists but only past `max_length` (a genuinely
    long lead sentence, confirmed to be real prose), falls back to
    truncate_at_word_boundary() rather than refusing outright.
    """
    text = _strip_body_boilerplate(body_text or "")
    if not text:
        return ""
    if not _RE_SENTENCE_END.search(text):
        return ""
    if len(text) <= max_length:
        return text
    for match in _RE_SENTENCE_END.finditer(text, 0, max_length + 1):
        end = match.end()
        if end >= min_length:
            return text[:end].strip()
    return truncate_at_word_boundary(text, max_length)


def improve_summary_from_body(current_summary: str, body_text: str) -> str:
    """
    Rule-based summary improvement (2026-07-13) — regenerates `summary`
    from `body_text` (RSS full-content or scraped) when the current
    summary is too short. Since full-text scraping was dropped from Read
    mode (2026-07-11), `summary` is now the *only* article content shown
    to users, so a one-sentence RSS teaser is no longer good enough on its
    own. Purely deterministic, no AI: extracts whole sentences from
    `body_text` rather than rewriting/expanding text, so nothing is
    invented and there's no hallucination risk.

    Always boilerplate-cleans `current_summary` too (via
    _strip_body_boilerplate), even when it's already long enough to skip
    extension — found 2026-07-13: some RSS feeds' own `summary`/
    `description` field already embeds full article text (site
    boilerplate included), so a summary can be "long enough" and still
    carry junk that was never touched by the length-based extension path
    below.
    """
    current = _strip_body_boilerplate((current_summary or "").strip())
    body = (body_text or "").strip()
    if len(current) >= MIN_SUMMARY_LENGTH or not body:
        return current
    if len(body) <= len(current):
        return current  # nothing to gain from body_text
    candidate = extract_summary_from_body(body)
    if len(candidate) > len(current):
        return candidate
    return current


def trim_trailing_partial_word(text: str) -> str:
    """
    For text already cut off mid-word by the old buggy plain `[:2000]`
    slice (before truncate_at_word_boundary existed) — trims the dangling
    partial word and appends "…". Unlike truncate_at_word_boundary, this
    assumes the text is already sitting at its length ceiling; it only
    cleans up an existing bad cut, used by the one-off DB backfill script.
    """
    if not text:
        return text
    last_space = text.rfind(" ")
    if last_space > 0:
        text = text[:last_space]
    return text.rstrip() + "…"


def _strip_truncation_artifacts(text: str) -> str:
    """
    Remove common publisher-side truncation markers ("[...]", "Continue
    reading...", WordPress's "The post X appeared first on Y." excerpt
    footer, trailing "...") from a already-cleaned summary/body_text string.
    These come from the RSS source itself, not from any slicing WhatsNews
    does — safe to strip since they carry no article content.
    """
    if not text:
        return text
    text = _RE_WORDPRESS_EXCERPT_FOOTER.sub("", text)
    text = _RE_BRACKET_ELLIPSIS.sub("", text)
    text = _RE_CONTINUE_READING.sub("", text)
    text = _RE_TRAILING_ELLIPSIS.sub("", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


def parse_published_at(entry) -> datetime | None:
    """
    Extract a timezone-aware UTC datetime from a feedparser entry.
    feedparser exposes parsed dates as time.struct_time in published_parsed
    (falling back to updated_parsed).  Returns None if unavailable/unparseable.
    """
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime.fromtimestamp(timegm(parsed), tz=ZoneInfo("UTC"))
        except Exception:
            pass

    raw = (entry.get("published") or entry.get("updated") or "").strip()
    if not raw:
        return None
    for fmt in _FALLBACK_DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=ZoneInfo("UTC"))
        except ValueError:
            continue
    return None


def parse_external_id(entry) -> str | None:
    """
    Extract a stable per-item identifier from a feedparser entry.
    feedparser maps an RSS <guid> / Atom <id> onto entry.id.  Falls back to
    an explicit `guid` field.  Returns None when nothing usable is present.
    """
    external_id = entry.get("id") or entry.get("guid")
    external_id = (external_id or "").strip()
    return external_id or None


def extract_image_url(entry) -> str | None:
    """
    Extract the best available image URL from a feedparser entry.
    Checks media:content, media:thumbnail, enclosures, and typed links in order.
    Returns None when no image is found.
    """
    for m in (entry.get("media_content") or []):
        url = (m.get("url") or "").strip()
        medium = (m.get("medium") or "").lower()
        if url and (not medium or medium == "image"):
            return url

    for m in (entry.get("media_thumbnail") or []):
        url = (m.get("url") or "").strip()
        if url:
            return url

    for enc in (entry.get("enclosures") or []):
        mime = (enc.get("type") or "").lower()
        url = (enc.get("href") or enc.get("url") or "").strip()
        if url and "image" in mime:
            return url

    for link in (entry.get("links") or []):
        mime = (link.get("type") or "").lower()
        url = (link.get("href") or "").strip()
        if url and "image" in mime:
            return url

    return None


def _extract_body_text(entry) -> str:
    """
    Extract the fullest available article text from a feedparser entry.
    feedparser stores full-content feeds under entry.content (a list of dicts
    with 'value' and 'type' keys).  Falls back to summary/description.
    Returns cleaned plain text, capped at 8000 chars to stay DB-friendly.
    """
    content_list = entry.get("content") or []
    for block in content_list:
        value = (block.get("value") or "").strip()
        if value:
            cleaned = _strip_body_boilerplate(_strip_truncation_artifacts(_clean_text(value)))
            if len(cleaned) > 100:  # only use if meaningfully longer than summary
                return cleaned[:8000]
    return ""


def normalize_rss_entry(entry, source: str = "") -> dict:
    """
    Standardize a single feedparser entry into:
      {
        "title": str,
        "summary": str,
        "body_text": str,          # full article text when feed provides it
        "url": str,
        "published_at": datetime | None,
        "source": str,
        "external_id": str | None,
        "image_url": str | None,
      }

    Missing fields degrade to "" or None rather than raising. The `source`
    argument lets the caller supply the feed-level source name; if omitted,
    it falls back to any source title carried on the entry itself.
    """
    title = _clean_text(entry.get("title") or "")

    raw_summary = entry.get("summary") or entry.get("description") or ""
    summary = _strip_truncation_artifacts(_clean_text(raw_summary))

    url = (entry.get("link") or "").strip()

    # Prefer an explicit source; otherwise try the entry's own source title.
    resolved_source = source
    if not resolved_source:
        entry_source = entry.get("source") or {}
        if isinstance(entry_source, dict):
            resolved_source = (entry_source.get("title") or "").strip()

    return {
        "title": title,
        "summary": summary,
        "body_text": _extract_body_text(entry),
        "url": url,
        "published_at": parse_published_at(entry),
        "source": resolved_source,
        "external_id": parse_external_id(entry),
        "image_url": extract_image_url(entry),
    }
