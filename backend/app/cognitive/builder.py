"""
Cognitive block builder (Phase 27).

Transforms a Phase 26 narrative block into a cognitive block:
  headline           — unchanged from Phase 26
  what_happened      — unchanged
  so_what            — "why should I care?" (derived from why_it_matters + score)
  impact_level       — critical / high / medium / low
  risk_level         — high / medium / low
  who_is_affected    — list of affected entities (companies, countries, sectors, institutions)
  action_implication — rule-based implication for the reader
  confidence         — 0–100
  signal_score       — inherited
  sources            — inherited
"""

from __future__ import annotations

import re

from app.cognitive.scoring import (
    compute_impact_level,
    compute_risk_level,
    compute_confidence,
)
from app.cognitive.templates import (
    ACTION_IMPLICATIONS,
    ACTION_IMPLICATION_FALLBACK,
    SO_WHAT_FALLBACK,
    IMPACT_TYPE_TO_SECTOR,
    ENTITY_MAP,
)

# ── so_what ───────────────────────────────────────────────────────────────────

def _build_so_what(narrative_block: dict, impact_level: str) -> str:
    """
    Derive "why should I care?" from existing narrative data.

    Priority:
    1. why_it_matters if it reads like interpretation (not just facts)
    2. Template based on impact_level
    """
    wim = (narrative_block.get("why_it_matters") or "").strip()

    # Use existing WIM if it's interpretive (>40 chars, not attribution)
    if len(wim) > 40 and not wim.startswith("According to"):
        # Make it more direct if it starts with "This"
        return wim

    # Derive from signal components via impact_level template
    return SO_WHAT_FALLBACK.get(impact_level, SO_WHAT_FALLBACK["medium"])


# ── who_is_affected ───────────────────────────────────────────────────────────

_BIGRAM_ENTITIES = {
    k: v for k, v in ENTITY_MAP.items() if " " in k
}
_UNIGRAM_ENTITIES = {
    k: v for k, v in ENTITY_MAP.items() if " " not in k
}


def _extract_entities_from_text(text: str) -> list[tuple[str, str]]:
    """
    Extract known named entities from text.
    Returns [(canonical_name, category), ...] deduplicated.
    """
    lower = text.lower()
    found: dict[str, str] = {}  # canonical → category

    # Bigram check first (e.g. "federal reserve", "world bank")
    for phrase, (cat, canonical) in _BIGRAM_ENTITIES.items():
        if phrase in lower and canonical not in found:
            found[canonical] = cat

    # Unigram check on word boundaries
    tokens = set(re.sub(r"[^\w\s]", "", lower).split())
    for token, (cat, canonical) in _UNIGRAM_ENTITIES.items():
        if token in tokens and canonical not in found:
            found[canonical] = cat

    return [(name, cat) for name, cat in found.items()]


def _build_who_is_affected(narrative_block: dict) -> list[str]:
    """
    Build a list of affected entity strings for the cognitive block.

    Sources:
    1. Named entity recognition on headline + top article titles
    2. Sector inference from editorial impact_types
    """
    texts = [narrative_block.get("headline", "")]
    for article in (narrative_block.get("top_articles") or [])[:3]:
        texts.append(article.get("title", ""))

    full_text = " ".join(texts)
    raw_entities = _extract_entities_from_text(full_text)

    # Deduplicate and order: institutions first, then companies, countries, sectors
    order = {"institution": 0, "company": 1, "country": 2, "sector": 3}
    raw_entities.sort(key=lambda e: order.get(e[1], 4))

    # Build display strings
    result: list[str] = []
    seen_names: set[str] = set()

    for name, cat in raw_entities:
        if name not in seen_names:
            seen_names.add(name)
            if cat == "sector":
                result.append(name)
            else:
                result.append(name)

    # Add sector inference from editorial_metadata.impact_types
    top_articles = narrative_block.get("top_articles") or []
    if top_articles:
        metadata = top_articles[0].get("editorial_metadata") or {}
        impact_types = metadata.get("impact_types") or []
        for itype in impact_types:
            sector = IMPACT_TYPE_TO_SECTOR.get(itype)
            if sector and sector not in seen_names:
                result.append(sector)
                seen_names.add(sector)

    # Cap at 6 entities (keep it scannable)
    return result[:6]


# ── action_implication ────────────────────────────────────────────────────────

def _build_action_implication(narrative_block: dict, impact_level: str) -> str:
    """
    Derive rule-based action implication from impact type + impact level.
    """
    top_articles = narrative_block.get("top_articles") or []
    if top_articles:
        metadata = top_articles[0].get("editorial_metadata") or {}
        impact_types = metadata.get("impact_types") or []
        for itype in impact_types:
            type_map = ACTION_IMPLICATIONS.get(itype)
            if type_map:
                return type_map.get(impact_level, type_map.get("medium", ""))

    return ACTION_IMPLICATION_FALLBACK.get(
        impact_level, ACTION_IMPLICATION_FALLBACK["medium"]
    )


# ── Main builder ──────────────────────────────────────────────────────────────

def build_cognitive_block(narrative_block: dict) -> dict:
    """
    Transform a Phase 26 narrative block into a cognitive intelligence block.

    Input:  narrative block dict from app.briefing.builder.build_narrative_block()
    Output: cognitive block dict with 5 new fields + inherited fields
    """
    signal_score  = narrative_block.get("signal_score", 0)
    impact_level  = compute_impact_level(signal_score)
    risk_level    = compute_risk_level(narrative_block)
    confidence    = compute_confidence(narrative_block)

    return {
        # Identity
        "headline":           narrative_block.get("headline", ""),
        "what_happened":      narrative_block.get("what_happened", ""),
        # Cognitive fields
        "so_what":            _build_so_what(narrative_block, impact_level),
        "impact_level":       impact_level,
        "risk_level":         risk_level,
        "who_is_affected":    _build_who_is_affected(narrative_block),
        "action_implication": _build_action_implication(narrative_block, impact_level),
        "confidence":         confidence,
        # Inherited signal metadata
        "signal_score":       signal_score,
        "signal_tier":        narrative_block.get("signal_tier", "informational"),
        "sources_count":      narrative_block.get("sources_count", 0),
        "sources":            narrative_block.get("sources", []),
        "supporting_article_count": narrative_block.get("supporting_article_count", 1),
        "top_articles":       narrative_block.get("top_articles", []),
    }
