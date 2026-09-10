"""
Narrative templates for Phase 26 briefing builder.

All templates are rule-based. No LLM required.
Templates are keyed to event signals detected in builder.py.
"""

from __future__ import annotations

# ── Why It Matters — by impact type ──────────────────────────────────────────

WIM_BY_IMPACT_TYPE: dict[str, str] = {
    "market_moving":   "This development has direct implications for markets and investors.",
    "geopolitical":    "This shift affects international relations and regional stability.",
    "tech_disruption": "This represents a significant change in the technology landscape.",
    "regulatory":      "This regulatory action will reshape industry practices and compliance.",
    "economic":        "This economic development has downstream effects on consumers and businesses.",
    "public_safety":   "This event directly affects public health and safety.",
    "governance":      "This governance decision sets precedent for future policy and regulation.",
}

WIM_BY_SIGNAL_BAND: dict[str, str] = {
    "critical":  "Exceptional significance — this event warrants close monitoring across sectors.",
    "high":      "High-impact development with broad downstream effects.",
    "moderate":  "Notable development with meaningful implications for affected stakeholders.",
    "low":       "An emerging development worth tracking for future relevance.",
}

# ── What Changed — by detected change pattern ─────────────────────────────────

CHANGE_BY_PATTERN: dict[str, str] = {
    "increase":    "A notable increase signals upward momentum from the prior baseline.",
    "decrease":    "A significant decline marks a departure from recent trajectory.",
    "restriction": "New restrictions represent a tightening of existing policy.",
    "approval":    "Official approval clears the path for implementation.",
    "acquisition": "A consolidation move reshapes the competitive landscape.",
    "new_launch":  "A new product or initiative enters the landscape, shifting competitive dynamics.",
    "reversal":    "A policy reversal indicates a strategic change in direction.",
    "escalation":  "An escalation marks a step-change from the previous status quo.",
    "default":     "A notable development has emerged that shifts the prior state.",
}

# ── Watch Next — by impact type ───────────────────────────────────────────────

WATCH_NEXT_BY_IMPACT: dict[str, str] = {
    "market_moving":   "Watch for: analyst revisions, trading volumes, and company guidance updates.",
    "geopolitical":    "Watch for: diplomatic responses, sanctions implementation, and allied reactions.",
    "tech_disruption": "Watch for: competitive responses, adoption rates, and regulatory scrutiny.",
    "regulatory":      "Watch for: enforcement timelines, legal challenges, and industry adaptation.",
    "economic":        "Watch for: central bank signals, employment data, and consumer confidence.",
    "public_safety":   "Watch for: official advisories, policy responses, and updated risk assessments.",
    "governance":      "Watch for: implementation rules, appeals, and precedent-setting follow-ons.",
    "acquisitions":    "Watch for: regulatory approval timeline, integration plan, and talent impact.",
}

WATCH_NEXT_BY_KEYWORD: list[tuple[str, str]] = [
    ("earnings",     "Watch for: guidance revisions, analyst upgrades/downgrades, and peer comparisons."),
    ("acquisition",  "Watch for: regulatory approval, integration timeline, and talent impact."),
    ("merger",       "Watch for: regulatory review, shareholder votes, and combined entity strategy."),
    ("recall",       "Watch for: affected unit counts, liability exposure, and remediation timeline."),
    ("election",     "Watch for: final results, transition timeline, and policy implications."),
    ("sanction",     "Watch for: enforcement actions, carve-outs, and trading partner reactions."),
    ("tariff",       "Watch for: retaliatory measures, supply chain shifts, and price pass-through."),
    ("bankruptcy",   "Watch for: creditor negotiations, asset sales, and workforce impact."),
    ("ipo",          "Watch for: post-IPO lock-up expiry, analyst coverage initiation, and trading volume."),
    ("launch",       "Watch for: early adoption signals, competitive reactions, and developer ecosystem."),
    ("ban",          "Watch for: enforcement mechanisms, legal challenges, and workarounds."),
    ("deal",         "Watch for: closing conditions, integration milestones, and strategic rationale."),
    ("war",          "Watch for: ceasefire negotiations, humanitarian corridor updates, and allied commitments."),
    ("default",      "Watch for: creditor responses, restructuring terms, and contagion risk."),
]

WATCH_NEXT_FALLBACK = (
    "Watch for: follow-on developments, official responses, and downstream market reactions "
    "in the coming 24–72 hours."
)

# ── Thread Labels (cross-event synthesis) ────────────────────────────────────

THREAD_LABEL_TEMPLATE = "Multiple signals converging around {entity}"
THREAD_DEFAULT_LABEL   = "Interconnected developments"
