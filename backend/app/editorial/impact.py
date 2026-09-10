"""Rule-based impact type detection (Phase 17.1)."""

from __future__ import annotations

IMPACT_TYPES: tuple[str, ...] = (
    "technology",
    "market",
    "business",
    "policy",
    "regulation",
    "geopolitics",
    "defense",
    "healthcare",
    "energy",
    "consumer",
)

IMPACT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "technology": [
        "software", "hardware", "chip", "semiconductor", "cloud", "ai",
        "artificial intelligence", "algorithm", "platform", "api", "data center",
        "cybersecurity", "startup", "open source", "llm", "model",
    ],
    "market": [
        "stock", "stocks", "bond", "yield", "fed", "inflation", "rate",
        "earnings", "ipo", "crypto", "bitcoin", "commodity", "treasury",
        "wall street", "trading", "index", "s&p", "nasdaq",
    ],
    "business": [
        "ceo", "merger", "acquisition", "layoff", "revenue", "profit",
        "corporate", "company", "enterprise", "workforce", "headquarters",
        "retailer", "shareholder", "quarterly",
    ],
    "policy": [
        "policy", "legislation", "congress", "parliament", "white house",
        "executive order", "mandate", "government", "administration",
        "federal", "state department",
    ],
    "regulation": [
        "regulation", "regulator", "regulatory", "compliance", "antitrust",
        "sec ", "ftc", "fda approval", "rulemaking", "enforce",
    ],
    "geopolitics": [
        "sanctions", "diplomacy", "nato", "war", "conflict", "treaty",
        "summit", "embassy", "foreign minister", "united nations",
        "china", "russia", "ukraine", "taiwan", "middle east", "iran", "israel",
    ],
    "defense": [
        "pentagon", "military", "weapon", "missile", "fighter", "navy",
        "army", "defense contract", "ndaa", "procurement", "drone", "uav",
    ],
    "healthcare": [
        "hospital", "patient", "pharma", "pharmaceutical", "drug", "vaccine",
        "clinical trial", "medicare", "medicaid", "biotech", "disease",
        "treatment", "therapy", "fda",
    ],
    "energy": [
        "oil", "gas", "opec", "pipeline", "lng", "refinery", "nuclear",
        "coal", "petroleum", "electricity", "grid", "renewable", "solar",
        "wind farm", "power plant",
    ],
    "consumer": [
        "consumer", "privacy", "subscription", "price increase", "recall",
        "product safety", "household", "shopping", "retail price", "users",
        "app store", "smartphone",
    ],
}


def detect_impact_types(title: str, summary: str) -> list[str]:
    """Return impact types whose keywords match title or summary (stable order)."""
    text = (title + " " + (summary or "")).lower()
    matched: list[str] = []
    for impact_type in IMPACT_TYPES:
        keywords = IMPACT_TYPE_KEYWORDS.get(impact_type, [])
        if any(kw in text for kw in keywords):
            matched.append(impact_type)
    return matched
