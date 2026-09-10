"""Cross-topic bridge keywords for editorial profiling (Phase 17.1)."""

from __future__ import annotations

# Curated bridges — expanded in Phase 17.4 for narrative synthesis.
CROSS_TOPIC_BRIDGES: list[dict] = [
    {
        "id": "ai_chips_markets",
        "keywords": [
            "nvidia", "semiconductor", "chip", "hbm", "memory",
            "export controls", "data center", "ai infrastructure",
        ],
        "label": "AI infrastructure and chip supply",
    },
    {
        "id": "energy_geopolitics",
        "keywords": [
            "opec", "sanctions", "pipeline", "lng", "strait",
            "embargo", "energy security",
        ],
        "label": "Energy security and geopolitical risk",
    },
    {
        "id": "healthcare_regulation",
        "keywords": [
            "fda", "medicare", "medicaid", "drug pricing",
            "clinical trial", "pharma regulation",
        ],
        "label": "Healthcare policy and regulation",
    },
    {
        "id": "defense_technology",
        "keywords": [
            "hypersonic", "drone", "autonomous weapons", "cyber warfare",
            "defense contract", "military ai",
        ],
        "label": "Defense and emerging technology",
    },
    {
        "id": "climate_markets",
        "keywords": [
            "carbon credit", "renewable investment", "climate policy",
            "green bond", "esg",
        ],
        "label": "Climate policy and market impact",
    },
]

ALL_BRIDGE_KEYWORDS: frozenset[str] = frozenset(
    kw for bridge in CROSS_TOPIC_BRIDGES for kw in bridge["keywords"]
)


def matches_any_bridge_keyword(title: str, summary: str) -> bool:
    text = (title + " " + (summary or "")).lower()
    return any(kw in text for kw in ALL_BRIDGE_KEYWORDS)


def detect_cross_topic_candidates(title: str, summary: str) -> list[str]:
    """
    Return human-readable bridge labels whose keywords appear in the article.
    """
    text = (title + " " + (summary or "")).lower()
    candidates: list[str] = []
    for bridge in CROSS_TOPIC_BRIDGES:
        if any(kw in text for kw in bridge["keywords"]):
            candidates.append(bridge["label"])
    return candidates
