"""Impact-aware rule-based WIM (Phase 17.2 fallback)."""

from __future__ import annotations

import re

IMPACT_MECHANISMS: dict[str, str] = {
    "market": (
        "investor expectations, pricing, and capital flows across related sectors"
    ),
    "policy": (
        "rule changes, compliance timelines, and how incentives shift for operators"
    ),
    "regulation": (
        "enforcement risk, compliance costs, and which business models stay viable"
    ),
    "technology": (
        "capability shifts, infrastructure bottlenecks, and adoption curves"
    ),
    "business": (
        "competitive positioning, margins, and how incumbents versus challengers respond"
    ),
    "geopolitics": (
        "strategic leverage, alliance dynamics, and cross-border supply chains"
    ),
    "defense": (
        "security posture, procurement cycles, and deterrence calculations"
    ),
    "healthcare": (
        "patient access, payer and provider economics, and clinical adoption paths"
    ),
    "energy": (
        "supply and demand balance, grid reliability, prices, and transition risk"
    ),
    "consumer": (
        "product behavior, privacy, cost to users, and everyday adoption friction"
    ),
}

WATCH_TEMPLATES: dict[str, str] = {
    "market": "Watch whether markets reprice related assets before the next data release.",
    "policy": "Watch for follow-on rulemaking or enforcement actions that clarify scope.",
    "regulation": "Watch whether regulators set a compliance deadline or penalty framework.",
    "technology": "Watch whether vendors ship upgrades that make this capability mainstream.",
    "business": "Watch competitor responses and whether guidance shifts next quarter.",
    "geopolitics": "Watch diplomatic statements and sanctions or trade measures that follow.",
    "defense": "Watch contract awards and deployment timelines tied to this development.",
    "healthcare": "Watch payer coverage decisions and whether clinical uptake accelerates.",
    "energy": "Watch production, inventory, and price moves in the next trading sessions.",
    "consumer": "Watch product rollouts, pricing changes, and user adoption signals.",
    "default": "Watch for official follow-up statements that confirm or narrow the scope.",
}


def _lead_clause(title: str, summary: str) -> str:
    title = (title or "").strip().rstrip(".")
    if summary:
        first = re.split(r"[.!?]\s+", summary.strip(), maxsplit=1)[0].strip()
        if len(first) >= 40:
            return first if first.endswith(".") else first + "."
    return f"{title}."


def _affected_parties(
    editorial_tags: list[str],
    source: str,
    topic: str,
) -> str:
    if editorial_tags:
        if len(editorial_tags) == 1:
            return editorial_tags[0]
        return f"{editorial_tags[0]} and peers in {topic}"
    if source:
        return f"readers tracking coverage from {source}"
    return f"stakeholders across {topic}"


def _pick_primary_impact(impact_types: list[str], topic: str) -> str:
    if impact_types:
        return impact_types[0]
    topic_defaults = {
        "Markets": "market",
        "Artificial Intelligence": "technology",
        "Technology": "technology",
        "Geopolitics": "geopolitics",
        "Defense": "defense",
        "Healthcare": "healthcare",
        "Energy": "energy",
        "Business": "business",
        "Climate Change": "energy",
        "Cybersecurity": "technology",
    }
    return topic_defaults.get(topic, "business")


def _build_watch_next(
    impact_type: str,
    editorial_tags: list[str],
    cross_topic_candidates: list[str],
) -> str:
    if cross_topic_candidates:
        thread = cross_topic_candidates[0]
        return f"Watch whether {thread.lower()} shows up in related coverage this week."
    if editorial_tags:
        tag = editorial_tags[0]
        return f"Watch {tag}'s next public move and any regulatory or market response."
    return WATCH_TEMPLATES.get(impact_type, WATCH_TEMPLATES["default"])


def generate_editorial_why_it_matters(
    *,
    title: str,
    summary: str,
    topic: str,
    source: str = "",
    editorial_metadata: dict | None = None,
) -> dict:
    """
    Build an impact-aware WIM paragraph without AI.

    Returns dict with why_it_matters, impact_type_used, watch_next, confidence.
    """
    meta = editorial_metadata or {}
    impact_types = list(meta.get("impact_types") or [])
    editorial_tags = list(meta.get("editorial_tags") or [])
    cross_topic_candidates = list(meta.get("cross_topic_candidates") or [])
    confidence = meta.get("confidence") or "medium"

    primary = _pick_primary_impact(impact_types, topic)
    impact_used = impact_types[:2] if impact_types else [primary]
    mechanism = IMPACT_MECHANISMS.get(primary, IMPACT_MECHANISMS["business"])
    affected = _affected_parties(editorial_tags, source, topic)
    watch_next = _build_watch_next(primary, editorial_tags, cross_topic_candidates)
    lead = _lead_clause(title, summary)

    why_it_matters = (
        f"{lead} "
        f"This matters because it affects {mechanism}, with direct consequences for {affected}. "
        f"{watch_next}"
    )

    return {
        "why_it_matters": why_it_matters.strip(),
        "impact_type_used": impact_used,
        "watch_next": watch_next,
        "confidence": confidence,
    }
