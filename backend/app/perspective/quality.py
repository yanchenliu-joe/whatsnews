"""Editorial perspective quality gate (Phase 17.3)."""

from __future__ import annotations

import re

from app.perspective.models import EditorialPerspective

BANNED_PHRASES: tuple[str, ...] = (
    "continued momentum",
    "growing momentum",
    "growing importance",
    "shows continued",
    "highlights growing",
    "this is important because",
    "important development",
    "significant shift",
    "could have implications",
    "worth watching",
)

MIN_PERSPECTIVE_WORDS = 100
MAX_PERSPECTIVE_WORDS = 240
MIN_HEADLINE_WORDS = 6
MAX_HEADLINE_WORDS = 18


def run_perspective_quality_gate(perspective: EditorialPerspective) -> dict:
    """
    Return {passed, errors, warnings}.
    Failure stores status=failed but does not block pipeline.
    """
    errors: list[str] = []
    warnings: list[str] = []

    evidence = perspective.supporting_evidence or []
    if len(evidence) < 3:
        errors.append("supporting_evidence_below_minimum")

    topics = {item.get("topic") for item in evidence if item.get("topic")}
    if len(topics) < 2:
        warnings.append("fewer_than_two_topics")

    watch = perspective.watch_next or []
    if len(watch) < 2:
        errors.append("watch_next_below_minimum")
    if len(watch) > 4:
        warnings.append("watch_next_above_recommended_max")

    if not perspective.confidence:
        errors.append("missing_confidence")

    headline_words = len((perspective.headline or "").split())
    if headline_words < MIN_HEADLINE_WORDS:
        errors.append("headline_too_short")
    if headline_words > MAX_HEADLINE_WORDS:
        warnings.append("headline_above_recommended_max")

    perspective_words = len((perspective.perspective or "").split())
    if perspective_words < MIN_PERSPECTIVE_WORDS:
        errors.append("perspective_too_short")
    if perspective_words > MAX_PERSPECTIVE_WORDS:
        warnings.append("perspective_above_recommended_max")

    lowered = (perspective.perspective or "").lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered or phrase in (perspective.headline or "").lower():
            errors.append(f"banned_phrase:{phrase}")

    if not _grounded_in_evidence(perspective):
        errors.append("insufficient_grounding")

    passed = len(errors) == 0
    return {"passed": passed, "errors": errors, "warnings": warnings}


def _grounded_in_evidence(perspective: EditorialPerspective) -> bool:
    """At least two supporting article topics or titles referenced in perspective text."""
    text = (perspective.perspective or "").lower()
    hits = 0
    for item in perspective.supporting_evidence or []:
        topic = (item.get("topic") or "").lower()
        title = (item.get("title") or "").lower()
        if topic and topic in text:
            hits += 1
            continue
        title_tokens = [t for t in re.findall(r"[a-z0-9]{4,}", title) if len(t) >= 5]
        if any(token in text for token in title_tokens[:3]):
            hits += 1
    return hits >= 2
