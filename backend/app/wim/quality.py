"""WIM quality gate (Phase 17.2)."""

from __future__ import annotations

import re

MIN_WIM_LENGTH = 80
MAX_WIM_LENGTH = 550

BANNED_GENERIC_PHRASES: tuple[str, ...] = (
    "continued momentum",
    "growing momentum",
    "continued interest",
    "shows continued",
    "highlights growing",
    "this is important because",
    "important development",
    "significant shift",
    "could have implications",
    "worth watching",
    "game-changer",
    "game changer",
    "landscape is changing",
    "on the surface",
    "incremental on the surface",
)

BANNED_WORDS: tuple[str, ...] = ("important", "significant", "crucial")

_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "that", "this", "will", "have",
        "been", "were", "are", "was", "has", "had", "not", "but", "into",
        "about", "after", "before", "their", "they", "them", "than", "then",
        "when", "what", "which", "while", "where", "would", "could", "should",
        "also", "more", "most", "some", "such", "over", "under", "between",
        "through", "during", "said", "says", "new", "news",
    }
)

WATCH_SIGNALS = (
    "watch", "monitor", "look for", "track", "await", "expect",
    "upcoming", "next", "whether",
)


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _significant_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-']+", text or ""):
        token = raw.lower().strip("'")
        if len(token) < 3 or token in _STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def _title_proper_nouns(title: str) -> set[str]:
    nouns: set[str] = set()
    for word in re.findall(r"\b[A-Z][a-zA-Z0-9\-']+\b", title or ""):
        if len(word) >= 2:
            nouns.add(word.lower())
    return nouns


def check_wim_quality(
    *,
    why_it_matters: str,
    title: str,
    summary: str,
    source: str,
    editorial_tags: list[str] | None = None,
    watch_next: str = "",
) -> tuple[bool, list[str]]:
    """
    Return (passed, quality_flags).
    Does not raise — callers decide fallback behavior.
    """
    flags: list[str] = []
    text = (why_it_matters or "").strip()
    lowered = _normalize(text)

    if len(text) < MIN_WIM_LENGTH:
        flags.append("too_short")
    if len(text) > MAX_WIM_LENGTH:
        flags.append("too_long")

    for phrase in BANNED_GENERIC_PHRASES:
        if phrase in lowered:
            flags.append(f"banned_phrase:{phrase}")

    for word in BANNED_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            flags.append(f"banned_word:{word}")

    title_tokens = _significant_tokens(title)
    summary_tokens = _significant_tokens(summary)
    wim_tokens = _significant_tokens(text)
    title_overlap = title_tokens & wim_tokens
    summary_overlap = summary_tokens & wim_tokens

    if len(title_overlap) < 1 and len(summary_overlap) < 1:
        flags.append("missing_grounding")
    elif len(title_overlap) < 1 and len(summary_overlap) < 2:
        flags.append("weak_grounding")

    has_actor = _has_concrete_actor(
        text=text,
        title=title,
        source=source,
        editorial_tags=editorial_tags or [],
    )
    if not has_actor:
        flags.append("missing_concrete_actor")

    has_watch = any(signal in lowered for signal in WATCH_SIGNALS)
    if watch_next.strip():
        watch_tokens = _significant_tokens(watch_next)
        if watch_tokens & wim_tokens:
            has_watch = True
    if not has_watch:
        flags.append("missing_watch_signal")

    hard_fail = {
        "too_short",
        "too_long",
        "missing_grounding",
    }
    hard_flags = {f.split(":")[0] for f in flags}
    banned_phrase_flags = [f for f in flags if f.startswith("banned_phrase:")]

    if hard_flags & hard_fail:
        return False, flags
    if banned_phrase_flags:
        return False, flags
    if "missing_concrete_actor" in flags:
        return False, flags
    if "weak_grounding" in flags:
        return False, flags

    return True, flags


def _has_concrete_actor(
    *,
    text: str,
    title: str,
    source: str,
    editorial_tags: list[str],
) -> bool:
    lowered = _normalize(text)
    if source and _normalize(source) in lowered:
        return True

    for tag in editorial_tags:
        if tag and tag.lower() in lowered:
            return True

    for noun in _title_proper_nouns(title):
        if noun in lowered:
            return True

    return False


def count_generic_phrase_blocks(flags: list[str]) -> int:
    return sum(1 for flag in flags if flag.startswith("banned_phrase:"))
