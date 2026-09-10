"""
Narrative block builder (Phase 26).

Transforms a Phase 25 event cluster into a structured narrative unit:
  headline       — ≤18-word neutral statement of what happened
  what_happened  — factual synthesis from top articles
  why_it_matters — significance interpretation
  what_changed   — delta from prior state
  watch_next     — forward-looking structured inference
  signal_score   — inherited from event
  sources        — list of source names
"""

from __future__ import annotations

import re

from app.briefing.templates import (
    WIM_BY_IMPACT_TYPE,
    WIM_BY_SIGNAL_BAND,
    CHANGE_BY_PATTERN,
    WATCH_NEXT_BY_IMPACT,
    WATCH_NEXT_BY_KEYWORD,
    WATCH_NEXT_FALLBACK,
)

# ── Change pattern detection ──────────────────────────────────────────────────

# Title-only patterns run first (more specific; avoids false matches from summary prose).
# Acquisition/reversal checked on title before generic increase/decrease on full text.
_TITLE_ONLY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(acquires?|acqui|buys?|purchases?|takeover|merger|merges?)\b"), "acquisition"),
    (re.compile(r"\b(reverses?|backtracks?|withdraws?|cancels?|scraps?)\b"),         "reversal"),
    (re.compile(r"\b(escalates?|escalation|retaliates?)\b"),                          "escalation"),
    (re.compile(r"\b(bans?|blocks?|restricts?|halts?|pauses?|prohibits?)\b"),         "restriction"),
    (re.compile(r"\b(approves?|authorizes?|clears?|greenlights?|permits?)\b"),        "approval"),
]

_FULLTEXT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(raises?|hikes?|increases?|surges?|soars?|jumps?)\b"), "increase"),
    (re.compile(r"\b(cuts?|slashes?|reduces?|plunges?|declines?|falls?|drops?)\b"),   "decrease"),
    (re.compile(r"\b(launches?|releases?|introduces?|unveils?)\b"),                    "new_launch"),
    (re.compile(r"\b(threatens?|warns?)\b"),                                           "escalation"),
]

# ── Entity extraction for cross-event synthesis ───────────────────────────────

_ENTITY_STOP_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "for", "to", "of", "and", "or",
    "but", "is", "are", "was", "were", "be", "been", "being", "with",
    "by", "from", "that", "this", "its", "it", "has", "have", "had",
    "as", "after", "before", "new", "over", "under", "into", "up",
})


def extract_entities(texts: list[str]) -> set[str]:
    """
    Extract likely named entities (proper nouns, acronyms) from text.
    Used for cross-event thread detection.
    """
    entities: set[str] = set()
    for text in texts:
        words = text.split()
        for word in words:
            clean = re.sub(r"[^\w]", "", word)
            if len(clean) < 2 or clean.lower() in _ENTITY_STOP_WORDS:
                continue
            # Acronym: 2–5 uppercase chars
            if 2 <= len(clean) <= 5 and clean.isupper():
                entities.add(clean)
            # Proper noun: title-case, ≥4 chars, not a common word
            elif len(clean) >= 4 and clean[0].isupper() and clean[1:].islower():
                entities.add(clean)
    return entities


# ── Headline ─────────────────────────────────────────────────────────────────

_HEADLINE_STRIP_PREFIXES = re.compile(
    r"^(BREAKING|EXCLUSIVE|ALERT|DEVELOPING|UPDATED?|JUST IN)[:\s–—-]+",
    re.IGNORECASE,
)

def _build_headline(event_title: str) -> str:
    title = _HEADLINE_STRIP_PREFIXES.sub("", event_title).strip()
    words = title.split()
    if len(words) <= 18:
        return title
    return " ".join(words[:18]) + "…"


# ── What Happened ─────────────────────────────────────────────────────────────

def _build_what_happened(event: dict) -> str:
    articles = event.get("top_articles") or []
    seen: set[str] = set()
    sentences: list[str] = []

    for a in articles[:3]:
        source = a.get("source") or ""
        # Prefer raw summary (factual), not why_it_matters (opinionated)
        text = (a.get("summary") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        # Attribute to source on first sentence only
        if not sentences and source:
            sentences.append(f"According to {source}: {text}")
        else:
            sentences.append(text)

    if sentences:
        return " ".join(sentences)

    # Fall back to event title if no summaries
    return event.get("event_title", "Details are emerging.")


# ── Why It Matters ────────────────────────────────────────────────────────────

def _build_why_it_matters(event: dict) -> str:
    # 1. Use the event's already-computed WIM text (best quality)
    wim = (event.get("summary") or "").strip()
    if wim and len(wim) > 30 and not wim.startswith("According to"):
        return wim

    # 2. Derive from top article's impact types
    top = event.get("top_articles", [{}])
    if top:
        metadata = top[0].get("editorial_metadata") or {}
        impact_types = metadata.get("impact_types") or []
        for itype in impact_types:
            if itype in WIM_BY_IMPACT_TYPE:
                return WIM_BY_IMPACT_TYPE[itype]

    # 3. Fall back to signal band description
    score = event.get("signal_score", 50)
    if score >= 90:
        return WIM_BY_SIGNAL_BAND["critical"]
    elif score >= 70:
        return WIM_BY_SIGNAL_BAND["high"]
    elif score >= 50:
        return WIM_BY_SIGNAL_BAND["moderate"]
    return WIM_BY_SIGNAL_BAND["low"]


# ── What Changed ──────────────────────────────────────────────────────────────

def _build_what_changed(event: dict) -> str:
    title = event.get("event_title", "").lower()
    articles = event.get("top_articles") or []
    summary_text = " ".join(
        (a.get("summary") or "").lower() for a in articles[:2]
    )
    full_text = title + " " + summary_text

    # Title-only check first (more precise signal)
    for pattern, change_type in _TITLE_ONLY_PATTERNS:
        if pattern.search(title):
            return CHANGE_BY_PATTERN[change_type]

    # Full-text check (summary can confirm increase/decrease/launch)
    for pattern, change_type in _FULLTEXT_PATTERNS:
        if pattern.search(full_text):
            return CHANGE_BY_PATTERN[change_type]

    # Numeric shift (percentage or dollar amount)
    if re.search(r"\d+[\.,]?\d*\s*(%|\$|bn|million|billion|trillion)", full_text):
        return "A measurable quantitative shift from the previous baseline has been reported."

    return CHANGE_BY_PATTERN["default"]


# ── Watch Next ────────────────────────────────────────────────────────────────

def _build_watch_next(event: dict) -> str:
    # 1. Match on editorial impact types from top article
    top = event.get("top_articles", [{}])
    if top:
        metadata = top[0].get("editorial_metadata") or {}
        impact_types = metadata.get("impact_types") or []
        for itype in impact_types:
            if itype in WATCH_NEXT_BY_IMPACT:
                return WATCH_NEXT_BY_IMPACT[itype]

    # 2. Match on keywords in event title
    title = event.get("event_title", "").lower()
    for keyword, watch_str in WATCH_NEXT_BY_KEYWORD:
        if keyword in title:
            return watch_str

    return WATCH_NEXT_FALLBACK


# ── Main builder ─────────────────────────────────────────────────────────────

def build_narrative_block(event: dict) -> dict:
    """
    Transform a Phase 25 event cluster into a structured narrative block.

    Input:  event dict from clustering.cluster_articles()
    Output: narrative block dict with headline, what_happened, why_it_matters,
            what_changed, watch_next, signal_score, sources_count, sources
    """
    return {
        "headline":       _build_headline(event.get("event_title", "")),
        "what_happened":  _build_what_happened(event),
        "why_it_matters": _build_why_it_matters(event),
        "what_changed":   _build_what_changed(event),
        "watch_next":     _build_watch_next(event),
        "signal_score":   event.get("signal_score", 0),
        "signal_tier":    event.get("signal_tier", "informational"),
        "sources_count":  event.get("sources_count", 0),
        "sources":        event.get("sources") or [],
        "supporting_article_count": event.get("supporting_article_count", 1),
        "top_articles":   event.get("top_articles") or [],
    }
