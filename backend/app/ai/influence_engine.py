"""Influence Engine — deterministic event-to-impact propagation layer.

Phase 23C: adds a lightweight causal reasoning layer on top of the Phase 23B
event detection system.

Design:
  Event → entity matching → sector classification → propagation chain → InfluenceNode

Rules:
  - EARNINGS_EVENT: company sector → downstream topics + sentiment direction
  - MACRO_EVENT:    Fed/rate direction → Markets → Technology → Crypto (secondary)
  - GEO_EVENT:      sanctions/supply chain → Technology + Markets volatility
  - AI_TECH_EVENT:  NVIDIA/OpenAI → AI → Tech → Markets (positive unless regulation)

Confidence:
  confidence = base_event_confidence × entity_match_strength
    base_event_confidence: 0.9 (event.confidence ≥ 0.8), else 0.6
    entity_match_strength: 1.0 (entity in registry), 0.7 (inferred from triggers)

Safety:
  - No hallucinated entities — only entities from the curated registry or event triggers
  - No randomness — fully deterministic
  - Max MAX_INFLUENCE_NODES per article
  - Never raises
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ai.event_detector import Event


# ─── Constants ────────────────────────────────────────────────────────────────

MAX_INFLUENCE_NODES = 3
_MIN_CONFIDENCE = 0.35   # nodes below this threshold are dropped

# Canonical direction → float mapping.
# "volatile" maps to 0.2 (slight positive bias, acknowledges market activity
# without committing to a direction). Used to build the global graph node dict.
_DIRECTION_TO_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
    "volatile": 0.2,
}


def get_direction_score(direction: str) -> float:
    """Safe conversion: impact_direction string → signed float sentiment score.

    Returns 0.0 for any unrecognised direction string.
    """
    return _DIRECTION_TO_SCORE.get(direction, 0.0)


# ─── Sector entity groups ─────────────────────────────────────────────────────
# Used to classify which detected companies belong to which propagation chain.
# Kept in sync with entity_extractor._COMPANIES (same names, lowercase).

_SEMICONDUCTOR: frozenset[str] = frozenset({
    "nvidia", "amd", "intel", "tsmc", "qualcomm", "broadcom",
    "arm", "asml", "sk hynix", "samsung",
})

_AI_LABS: frozenset[str] = frozenset({
    "openai", "anthropic", "deepmind", "xai", "mistral", "cohere",
    "stability ai", "hugging face", "inflection",
})

_BIG_TECH: frozenset[str] = frozenset({
    "apple", "microsoft", "alphabet", "google", "meta", "amazon",
    "ibm", "oracle", "salesforce", "adobe", "palantir",
})

_CHINA_TECH: frozenset[str] = frozenset({
    "alibaba", "tencent", "bytedance", "huawei", "baidu", "xiaomi",
})

_FINANCE_COS: frozenset[str] = frozenset({
    "jpmorgan", "goldman sachs", "blackrock", "citadel",
    "bridgewater", "morgan stanley", "bank of america",
})


# ─── Sentiment signal tables ──────────────────────────────────────────────────
# Single-word or phrase triggers (matched against lowercased article text).

_EARNINGS_POSITIVE: frozenset[str] = frozenset({
    "beat", "exceeded", "record", "growth", "raised guidance",
    "outperform", "strong", "surge", "accelerate", "positive",
    "better than expected", "blowout", "raised forecast",
})

_EARNINGS_NEGATIVE: frozenset[str] = frozenset({
    "miss", "cut guidance", "declined", "below expectations",
    "lowered", "weak", "disappointing", "worse than expected",
    "lowered forecast", "revenue shortfall", "write-down",
})

_RATE_POSITIVE: frozenset[str] = frozenset({
    "rate cut", "lower rate", "easing", "dovish", "pause",
    "pivot", "reducing rate", "cutting rate",
})

_RATE_NEGATIVE: frozenset[str] = frozenset({
    "rate hike", "raise rate", "tightening", "hawkish",
    "higher rate", "aggressive hike", "rate increase",
})

_AI_NEGATIVE_MODIFIERS: frozenset[str] = frozenset({
    # Word-boundary-safe: all entries are at least 4 chars and unlikely to be
    # substrings of neutral words. "cap" removed — matches "capabilities".
    "regulation", "ban ", "antitrust", "fine ", "restrict",
    "blockade", "lawsuit", "probe", "crackdown", "embargo",
    "penalt", "sanction",
})


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class InfluenceNode:
    """A single causal propagation path from an event to affected topics."""
    source_event: "Event"
    target_entities: list[str]          # Companies/actors driving the influence
    affected_topics: list[str]          # Topic labels that will feel the impact
    impact_type: str                    # earnings | macro | supply_chain | geopolitical | tech_adoption
    impact_direction: str               # positive | negative | neutral | volatile
    confidence: float                   # base_event_confidence × entity_match_strength
    reason: str                         # Human-readable propagation explanation


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _detect_direction(
    text: str,
    pos_signals: frozenset[str],
    neg_signals: frozenset[str],
    default: str = "neutral",
) -> str:
    """Single-pass sentiment probe — counts positive vs negative signal matches."""
    pos = sum(1 for s in pos_signals if s in text)
    neg = sum(1 for s in neg_signals if s in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return default


def _base_confidence(event: "Event") -> float:
    """Map event confidence to a binary base tier: 0.9 (strong) or 0.6 (weak)."""
    return 0.9 if event.confidence >= 0.8 else 0.6


def _entity_strength(entity: str, extracted_names: set[str]) -> float:
    """1.0 if entity is registry-validated; 0.7 if only inferred from triggers."""
    return 1.0 if entity in extracted_names else 0.7


def _best_strength(entities: list[str], extracted_names: set[str]) -> float:
    """Return the highest entity_match_strength across a list of entities."""
    if not entities:
        return 0.7
    return max(_entity_strength(e, extracted_names) for e in entities)


def _sector_entities(event_entities: list[str], sector: frozenset[str]) -> list[str]:
    """Filter event entities that belong to a given sector set."""
    return [e for e in event_entities if e in sector]


# ─── Rule handlers ────────────────────────────────────────────────────────────

def _handle_earnings(
    text: str,
    event: "Event",
    extracted_names: set[str],
) -> list["InfluenceNode"]:
    """
    EARNINGS_EVENT propagation.

    Sector-aware: same earnings event has different downstream impact depending
    on whether the company is a semiconductor maker, AI lab, big tech, or finance.
    """
    base = _base_confidence(event)
    direction = _detect_direction(text, _EARNINGS_POSITIVE, _EARNINGS_NEGATIVE)
    nodes: list[InfluenceNode] = []

    # Sector → (affected_topics, impact_type label)
    sector_map: list[tuple[frozenset[str], list[str], str]] = [
        (_SEMICONDUCTOR, ["AI", "Technology", "Markets"], "earnings:semiconductor"),
        (_AI_LABS,       ["AI", "Technology"],            "earnings:ai_lab"),
        (_BIG_TECH,      ["Technology", "Markets"],       "earnings:big_tech"),
        (_FINANCE_COS,   ["Markets"],                     "earnings:finance"),
    ]

    for sector, topics, impact_type in sector_map:
        matched = _sector_entities(event.entities, sector)
        if not matched:
            continue
        strength = _best_strength(matched, extracted_names)
        conf = round(base * strength, 2)
        if conf < _MIN_CONFIDENCE:
            continue
        names = ", ".join(matched[:2])
        topic_str = "/".join(topics)
        nodes.append(InfluenceNode(
            source_event=event,
            target_entities=matched,
            affected_topics=topics,
            impact_type=impact_type,
            impact_direction=direction,
            confidence=conf,
            reason=(
                f"{impact_type}: {names} earnings {direction} "
                f"→ {topic_str} impact"
            ),
        ))

    # Fallback: earnings event with no classified companies → Markets only
    if not nodes and event.entities:
        strength = _best_strength(event.entities, extracted_names)
        conf = round(base * strength, 2)
        if conf >= _MIN_CONFIDENCE:
            nodes.append(InfluenceNode(
                source_event=event,
                target_entities=event.entities[:3],
                affected_topics=["Markets"],
                impact_type="earnings",
                impact_direction=direction,
                confidence=conf,
                reason=f"earnings event → Markets {direction}",
            ))

    return nodes


def _handle_macro(
    text: str,
    event: "Event",
    extracted_names: set[str],
) -> list["InfluenceNode"]:
    """
    MACRO_EVENT propagation.

    Rate direction detection drives the impact chain:
      rate hike → negative for Markets / Technology / Crypto
      rate cut  → positive for Markets / Technology / Crypto
      neutral   → neutral with secondary effects
    """
    base = _base_confidence(event)
    direction = _detect_direction(text, _RATE_POSITIVE, _RATE_NEGATIVE, default="neutral")

    # Propagation chain: Fed → Markets → Tech → Crypto (secondary)
    # Crypto is only included when direction is clearly negative (risk-off)
    affected: list[str]
    if direction in ("positive", "negative"):
        affected = ["Markets", "Technology", "Crypto"]
    else:
        affected = ["Markets"]

    # Central bank entities are institutions, always partial-match risk
    fed_entities = [e for e in event.entities if e in {"fed", "federal reserve", "ecb", "fomc"}]
    target = fed_entities or event.entities[:2]
    strength = _best_strength(target, extracted_names)
    conf = round(base * strength, 2)

    if conf < _MIN_CONFIDENCE:
        return []

    rate_desc = "rate cut" if direction == "positive" else ("rate hike" if direction == "negative" else "rate signal")
    return [InfluenceNode(
        source_event=event,
        target_entities=target,
        affected_topics=affected,
        impact_type="macro",
        impact_direction=direction,
        confidence=conf,
        reason=(
            f"macro:Fed {rate_desc} → {'/'.join(affected)} {direction} pressure"
        ),
    )]


def _handle_geo(
    text: str,
    event: "Event",
    extracted_names: set[str],
) -> list["InfluenceNode"]:
    """
    GEO_EVENT propagation.

    Geopolitical events typically cause volatility. Taiwan/semiconductor supply
    chain risk gets its own node. China tech sanctions → Technology + Markets.
    """
    base = _base_confidence(event)
    nodes: list[InfluenceNode] = []

    # Supply chain node: Taiwan strait / export control / semiconductor restriction
    supply_chain_triggers = {"taiwan", "export control", "chips act", "semiconductor restriction"}
    has_supply_chain = any(t in text for t in supply_chain_triggers)
    if has_supply_chain:
        semi_entities = _sector_entities(event.entities, _SEMICONDUCTOR)
        geo_actors = [e for e in event.entities if e in {"china", "us", "taiwan"}]
        target = semi_entities + [e for e in geo_actors if e not in semi_entities]
        if target:
            strength = _best_strength(target, extracted_names)
            conf = round(base * strength, 2)
            if conf >= _MIN_CONFIDENCE:
                nodes.append(InfluenceNode(
                    source_event=event,
                    target_entities=target[:4],
                    affected_topics=["Technology", "Markets", "AI"],
                    impact_type="supply_chain",
                    impact_direction="negative",
                    confidence=conf,
                    reason=(
                        "geo:supply_chain — semiconductor/export control risk "
                        f"({', '.join(target[:2])}) → Tech/Markets/AI negative"
                    ),
                ))

    # General geopolitical volatility node
    geo_entities = [e for e in event.entities if e in {"china", "us", "russia", "nato", "taiwan", "ukraine"}]
    target_geo = geo_entities or event.entities[:3]
    if target_geo:
        strength = _best_strength(target_geo, extracted_names)
        conf = round(base * strength, 2)
        if conf >= _MIN_CONFIDENCE:
            nodes.append(InfluenceNode(
                source_event=event,
                target_entities=target_geo[:3],
                affected_topics=["Geopolitics", "Markets"],
                impact_type="geopolitical",
                impact_direction="volatile",
                confidence=conf,
                reason=(
                    f"geo:geopolitical — {', '.join(target_geo[:2])} tension "
                    "→ Geopolitics/Markets volatile"
                ),
            ))

    return nodes


def _handle_ai_tech(
    text: str,
    event: "Event",
    extracted_names: set[str],
) -> list["InfluenceNode"]:
    """
    AI_TECH_EVENT propagation.

    Generally positive (new model, product launch, chip release).
    Flips to negative if regulation/ban/antitrust keywords detected.
    """
    base = _base_confidence(event)
    # Pad text with spaces so trailing-space entries ("ban ", "fine ") match at end too
    padded = f" {text} "
    is_regulated = any(mod in padded for mod in _AI_NEGATIVE_MODIFIERS)
    direction = "negative" if is_regulated else "positive"

    nodes: list[InfluenceNode] = []

    # Semiconductor entities → hardware infrastructure chain
    semi_entities = _sector_entities(event.entities, _SEMICONDUCTOR)
    if semi_entities:
        strength = _best_strength(semi_entities, extracted_names)
        conf = round(base * strength, 2)
        if conf >= _MIN_CONFIDENCE:
            nodes.append(InfluenceNode(
                source_event=event,
                target_entities=semi_entities,
                affected_topics=["AI", "Technology", "Markets"],
                impact_type="tech_adoption",
                impact_direction=direction,
                confidence=conf,
                reason=(
                    f"ai_tech:hardware — {', '.join(semi_entities[:2])} "
                    f"AI chip/GPU → AI/Tech/Markets {direction}"
                ),
            ))

    # AI lab entities → software/model chain
    ai_entities = _sector_entities(event.entities, _AI_LABS)
    if ai_entities:
        strength = _best_strength(ai_entities, extracted_names)
        conf = round(base * strength, 2)
        if conf >= _MIN_CONFIDENCE:
            nodes.append(InfluenceNode(
                source_event=event,
                target_entities=ai_entities,
                affected_topics=["AI", "Technology"],
                impact_type="tech_adoption",
                impact_direction=direction,
                confidence=conf,
                reason=(
                    f"ai_tech:software — {', '.join(ai_entities[:2])} "
                    f"model/platform → AI/Tech {direction}"
                ),
            ))

    # Fallback: AI event with no classified entities → generic AI/Tech node
    if not nodes:
        target = event.entities[:3]
        strength = _best_strength(target, extracted_names) if target else 0.7
        conf = round(base * strength, 2)
        if conf >= _MIN_CONFIDENCE:
            nodes.append(InfluenceNode(
                source_event=event,
                target_entities=target,
                affected_topics=["AI", "Technology"],
                impact_type="tech_adoption",
                impact_direction=direction,
                confidence=conf,
                reason=f"ai_tech:event → AI/Tech {direction}",
            ))

    return nodes


# ─── Dispatcher ───────────────────────────────────────────────────────────────

_HANDLERS = {
    "EARNINGS_EVENT": _handle_earnings,
    "MACRO_EVENT":    _handle_macro,
    "GEO_EVENT":      _handle_geo,
    "AI_TECH_EVENT":  _handle_ai_tech,
}


# ─── Deduplication ────────────────────────────────────────────────────────────

def _dedup_nodes(nodes: list[InfluenceNode]) -> list[InfluenceNode]:
    """
    Collapse overlapping influence paths.

    Two nodes overlap when they share the same impact_type AND the same set of
    affected_topics. When overlap is detected, keep the higher-confidence node.
    """
    seen: dict[tuple, InfluenceNode] = {}
    for node in nodes:
        key = (node.impact_type, frozenset(node.affected_topics))
        existing = seen.get(key)
        if existing is None or node.confidence > existing.confidence:
            seen[key] = node
    return list(seen.values())


# ─── Public API ───────────────────────────────────────────────────────────────

def build_influence_nodes(
    text: str,
    extracted_entities,           # list[ExtractedEntity] — avoid circular import
    events: list,                 # list[Event]
    article_url: str = "",        # Phase 23D: used as edge source identifier
) -> list[InfluenceNode]:
    """
    Generate influence propagation nodes from detected events and feed
    them into the global graph singleton (Phase 23D).

    Pipeline (all in-memory, no DB):
      1. Build extracted entity name set for strength scoring
      2. For each event, invoke the matching rule handler
      3. Deduplicate overlapping propagation paths
      4. Sort by confidence, cap at MAX_INFLUENCE_NODES
      5. Merge nodes + edges into global_graph singleton

    Never raises. Returns [] on any failure.
    """
    if not events or not text:
        return []

    try:
        text_lower = text.lower()
        extracted_names: set[str] = {e.name.lower() for e in extracted_entities}

        raw_nodes: list[InfluenceNode] = []
        for event in events:
            handler = _HANDLERS.get(event.event_type)
            if handler is None:
                continue
            raw_nodes.extend(handler(text_lower, event, extracted_names))

        deduped = _dedup_nodes(raw_nodes)
        deduped.sort(key=lambda n: n.confidence, reverse=True)
        result = deduped[:MAX_INFLUENCE_NODES]

        # ── Phase 23D: feed nodes into global graph (FINAL BUILD) ────────────
        # Deferred import avoids circular-import risk at module load time.
        # global_graph.merge_node expects a plain dict (spec §3):
        #   entities, sentiment (float), confidence, topics, article_id
        try:
            from app.ai.global_graph import global_graph

            article_id = article_url or "unknown"
            for node in result:
                # Convert InfluenceNode → dict conforming to GlobalGraph.merge_node spec.
                # Use get_direction_score() to guarantee float; never pass a raw string.
                node_dict: dict = {
                    "entities":   node.target_entities,
                    "sentiment":  get_direction_score(node.impact_direction),
                    "confidence": float(node.confidence),
                    "topics":     node.affected_topics,
                    "article_id": article_id,
                }
                global_graph.merge_node(node_dict)

                # Article → entity edges
                for entity in node.target_entities:
                    global_graph.add_edge(
                        source=article_id,
                        target=entity,
                        relation_type=node.impact_type,
                        weight=node.confidence,
                        confidence=node.confidence,
                    )
        except Exception:
            pass  # global graph failure must never block influence generation

        return result

    except Exception:
        return []
