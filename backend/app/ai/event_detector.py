"""Event Detector — deterministic, single-pass event classification.

Design principles (Phase 23B):
  - Zero ML, zero external APIs
  - Single scan per event type (O(events × text) overall)
  - Events drive cross-topic mapping: event_type → affected topics
  - Entity refinement: entities detected in article narrow topic scope
  - Duplicate events are suppressed (one event_type per article max)
  - Confidence is rule-based: more trigger matches → higher confidence
  - Always safe: never raises, returns [] on any input problem
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.entity_extractor import ExtractedEntity


# ─── Event model ──────────────────────────────────────────────────────────────

@dataclass
class Event:
    """A detected semantic event in the article."""
    event_type: str            # EARNINGS_EVENT | MACRO_EVENT | GEO_EVENT | AI_TECH_EVENT
    entities: list[str]        # Entity names that triggered / are relevant to this event
    topics: list[str]          # Affected topic labels (generic: "Markets", "AI", etc.)
    confidence: float          # 0.0–1.0; min(1.0, trigger_matches / threshold)
    reason: str                # Human-readable explanation (logged, not sent to LLM)


# ─── Event rule definitions ───────────────────────────────────────────────────
# Each rule: triggers (any match activates) + base topics + entity refinement rules.
#
# Entity refinement: if a company from a specific sector is present, add its
# topic to the affected list. E.g. NVIDIA in an EARNINGS_EVENT adds "AI".
#
# confidence_threshold: number of trigger matches that gives confidence = 1.0.

_COMPANY_SECTOR_TOPICS: dict[str, list[str]] = {
    # Company name (lowercased) → extra topics to add if that company is mentioned
    "nvidia": ["AI", "Technology"],
    "amd": ["Technology"],
    "intel": ["Technology"],
    "tsmc": ["Technology"],
    "qualcomm": ["Technology"],
    "broadcom": ["Technology"],
    "openai": ["AI"],
    "anthropic": ["AI"],
    "apple": ["Technology"],
    "microsoft": ["Technology", "AI"],
    "alphabet": ["Technology", "AI"],
    "google": ["Technology", "AI"],
    "meta": ["Technology", "AI"],
    "amazon": ["Technology"],
    "tesla": ["Technology"],
}

@dataclass(frozen=True)
class _EventRule:
    event_type: str
    triggers: tuple[str, ...]       # Keywords; any match activates
    base_topics: tuple[str, ...]    # Topics always affected
    confidence_threshold: int = 2   # Trigger matches for confidence = 1.0


_EVENT_RULES: list[_EventRule] = [
    # ── Phase 23B spec: EARNINGS_EVENT ───────────────────────────────────────
    _EventRule(
        event_type="EARNINGS_EVENT",
        triggers=(
            "earnings", "revenue", "profit", "guidance", "downgrade", "upgrade",
            "eps ", "quarterly result", "beat estimate", "miss estimate",
            "full-year forecast", "raised guidance", "lowered guidance",
            "fiscal year", "operating income", "gross margin", "net income",
        ),
        base_topics=("Markets",),
        confidence_threshold=2,
    ),
    # ── Phase 23B spec: MACRO_EVENT ──────────────────────────────────────────
    _EventRule(
        event_type="MACRO_EVENT",
        triggers=(
            "fed ", "federal reserve", "interest rate", "inflation", "cpi ",
            "unemployment", "gdp ", "monetary policy", "rate hike", "rate cut",
            "quantitative easing", "quantitative tightening", "fomc",
            "consumer price", "labor market", "jobs report",
        ),
        base_topics=("Markets",),
        confidence_threshold=1,
    ),
    # ── Phase 23B spec: GEO_EVENT ────────────────────────────────────────────
    _EventRule(
        event_type="GEO_EVENT",
        triggers=(
            "china", "sanction", "export control", "tariff", "trade war",
            "war ", "invasion", "military strike", "embargo", "blockade",
            "diplomatic", "alliance ", "g7 ", "g20 ", "taiwan strait",
            "nato ", "un security", "nuclear ",
        ),
        base_topics=("Geopolitics", "Markets"),
        confidence_threshold=2,
    ),
    # ── Phase 23B spec: AI_TECH_EVENT ────────────────────────────────────────
    _EventRule(
        event_type="AI_TECH_EVENT",
        triggers=(
            "openai", "nvidia", "gpu ", "llm ", "ai model", "gpt",
            "foundation model", "model training", "inference chip", "ai chip",
            "large language", "diffusion model", "transformer model",
            "anthropic", "deepmind", "gemini", "claude", "machine learning",
        ),
        base_topics=("AI", "Technology", "Markets"),
        confidence_threshold=2,
    ),
]


# ─── Detection engine ─────────────────────────────────────────────────────────

def detect_events(
    text: str,
    entities: list[ExtractedEntity],
) -> list[Event]:
    """
    Run all event rules against the article text in a single pass.

    Steps:
      1. Lowercase the text once
      2. For each rule, count trigger matches (O(triggers × text))
      3. If any trigger matched, create an Event with confidence + entity refinement
      4. Deduplicate: at most one Event per event_type
      5. Return events sorted by confidence descending

    Never raises. Returns [] on any failure.
    """
    if not text:
        return []

    text_lower = text.lower()
    entity_names_lower = {e.name.lower() for e in entities}
    company_entities = {e.name.lower() for e in entities if e.category == "company"}

    events: list[Event] = []
    seen_types: set[str] = set()

    for rule in _EVENT_RULES:
        if rule.event_type in seen_types:
            continue

        # Single-pass trigger counting
        matched_triggers: list[str] = []
        for trigger in rule.triggers:
            if trigger in text_lower:
                matched_triggers.append(trigger.strip())

        if not matched_triggers:
            continue

        # Confidence: linear scale capped at 1.0
        confidence = min(1.0, len(matched_triggers) / rule.confidence_threshold)

        # Entity refinement: extend topics based on detected company sector
        extra_topics: list[str] = []
        relevant_entities: list[str] = []
        for company in company_entities:
            sector_topics = _COMPANY_SECTOR_TOPICS.get(company, [])
            extra_topics.extend(sector_topics)
            if sector_topics or company in " ".join(matched_triggers):
                relevant_entities.append(company)

        # Merge base + extra topics (dedup, preserve order)
        all_topics: list[str] = []
        seen_topics: set[str] = set()
        for t in list(rule.base_topics) + extra_topics:
            if t not in seen_topics:
                all_topics.append(t)
                seen_topics.add(t)

        # Build entity list: relevant companies + other matched entities
        event_entities: list[str] = relevant_entities[:5]
        for name in entity_names_lower:
            if name not in event_entities and len(event_entities) < 8:
                event_entities.append(name)

        # Safety: skip events with no clear signal
        if not event_entities and confidence < 0.4:
            continue

        reason = (
            f"{rule.event_type}: matched [{', '.join(matched_triggers[:3])}]"
            + (f" | entities: {event_entities[:3]}" if event_entities else "")
        )

        events.append(Event(
            event_type=rule.event_type,
            entities=event_entities,
            topics=all_topics,
            confidence=round(confidence, 2),
            reason=reason,
        ))
        seen_types.add(rule.event_type)

    # Sort by confidence descending so highest-quality events come first
    events.sort(key=lambda e: e.confidence, reverse=True)
    return events
