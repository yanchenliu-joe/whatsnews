"""
Cognitive layer templates (Phase 27).

All copy strings for action_implication and so_what generation.
Keyed by (impact_type, impact_level) for maximum specificity.
"""

from __future__ import annotations

# ── Action implications ────────────────────────────────────────────────────────
# Outer key: editorial impact_type. Inner key: impact_level.

ACTION_IMPLICATIONS: dict[str, dict[str, str]] = {
    "market_moving": {
        "critical": "Expect significant market repricing — monitor position exposure and hedging strategies.",
        "high":     "Market-sensitive development — volatility likely in directly affected sectors.",
        "medium":   "May weigh on sector sentiment; watch analyst commentary and trading volumes.",
        "low":      "Monitor for potential market implications as the situation develops.",
    },
    "geopolitical": {
        "critical": "Geopolitical risk materially elevated — supply chains, energy, and safe-haven assets affected.",
        "high":     "Diplomatic and economic spillovers likely; monitor allied responses and sanctions risk.",
        "medium":   "Regional stability implications — watch for policy responses and trade flow disruption.",
        "low":      "Geopolitical development to track; limited immediate cross-border impact.",
    },
    "tech_disruption": {
        "critical": "Competitive landscape significantly altered — strategic reassessment warranted for incumbents.",
        "high":     "Technology dynamics shifting; watch for follow-on product announcements and talent moves.",
        "medium":   "Innovation cycle advancing in this sector; monitor competitive and regulatory responses.",
        "low":      "Early-stage signal — track for adoption indicators and enterprise interest.",
    },
    "regulatory": {
        "critical": "Compliance review urgently warranted — enforcement risk is elevated and imminent.",
        "high":     "Regulatory pressure increasing — legal and compliance teams should prepare for disclosure.",
        "medium":   "Policy direction becoming clearer; monitor implementation timeline and carve-outs.",
        "low":      "Regulatory development to track; limited immediate operational impact.",
    },
    "economic": {
        "critical": "Macro environment materially shifting — review financial planning and rate assumptions.",
        "high":     "Economic conditions changing — interest rate and credit expectations are affected.",
        "medium":   "Economic indicator worth monitoring; watch for trend confirmation in next data release.",
        "low":      "Early economic signal; context-dependent interpretation.",
    },
    "public_safety": {
        "critical": "Public health or safety risk elevated — monitor official advisories and operational exposure.",
        "high":     "Safety implications likely to trigger regulatory and operational responses.",
        "medium":   "Safety development with sector-specific operational implications.",
        "low":      "Monitor for follow-on safety advisories.",
    },
    "governance": {
        "critical": "Governance framework materially changing — precedent-setting regulatory implications ahead.",
        "high":     "Policy direction shifting — compliance and regulatory implications across the sector.",
        "medium":   "Governance development with longer-term sector relevance.",
        "low":      "Policy signal to track for directional confirmation.",
    },
}

ACTION_IMPLICATION_FALLBACK: dict[str, str] = {
    "critical": "Significant development with broad downstream implications — monitor closely.",
    "high":     "High-impact event likely to generate follow-on reactions across affected sectors.",
    "medium":   "Notable development worth monitoring for broader market and policy implications.",
    "low":      "Early-stage signal; watch for confirmation and escalation over the coming days.",
}

# ── So What — by signal band (last-resort fallback) ──────────────────────────

SO_WHAT_FALLBACK: dict[str, str] = {
    "critical": "This is one of the most consequential developments today — broad, immediate impact expected.",
    "high":     "This matters because it directly reshapes the conditions that drive this sector.",
    "medium":   "Worth tracking: incremental but meaningful shift in the landscape.",
    "low":      "Limited immediate impact, but sets a precedent worth watching.",
}

# ── Risk keyword sets ─────────────────────────────────────────────────────────

HIGH_RISK_KEYWORDS = frozenset({
    "war", "invasion", "sanction", "sanctions", "coup", "nuclear", "conflict",
    "crash", "collapse", "bankruptcy", "default", "recession", "crisis",
    "attack", "explosion", "pandemic", "epidemic", "disaster", "assassination",
    "embargo", "blockade", "impeach", "indictment", "arrested",
})

MEDIUM_RISK_KEYWORDS = frozenset({
    "ban", "fine", "investigation", "lawsuit", "probe", "regulation", "restrict",
    "shortage", "recall", "warning", "threat", "escalation", "decline",
    "layoffs", "fired", "downgrade", "cuts", "tariff", "penalty", "suspended",
    "fraud", "breach", "hack", "leak",
})

# ── Sector inference from editorial impact types ──────────────────────────────

IMPACT_TYPE_TO_SECTOR: dict[str, str] = {
    "tech_disruption": "Technology sector",
    "market_moving":   "Financial markets",
    "regulatory":      "Regulated industries",
    "economic":        "Broader economy",
    "geopolitical":    "International relations",
    "public_safety":   "Public institutions",
    "governance":      "Government and policy",
    "acquisitions":    "M&A and capital markets",
}

# ── Named entity recognition map ─────────────────────────────────────────────
# Maps lowercase token(s) → (category, canonical display name)
# category: "company" | "country" | "institution" | "sector"

ENTITY_MAP: dict[str, tuple[str, str]] = {
    # Companies — Tech
    "apple":          ("company",     "Apple"),
    "google":         ("company",     "Google"),
    "alphabet":       ("company",     "Alphabet"),
    "meta":           ("company",     "Meta"),
    "amazon":         ("company",     "Amazon"),
    "microsoft":      ("company",     "Microsoft"),
    "tesla":          ("company",     "Tesla"),
    "openai":         ("company",     "OpenAI"),
    "nvidia":         ("company",     "Nvidia"),
    "intel":          ("company",     "Intel"),
    "amd":            ("company",     "AMD"),
    "qualcomm":       ("company",     "Qualcomm"),
    "samsung":        ("company",     "Samsung"),
    "tsmc":           ("company",     "TSMC"),
    "bytedance":      ("company",     "ByteDance"),
    "tiktok":         ("company",     "TikTok"),
    "uber":           ("company",     "Uber"),
    "airbnb":         ("company",     "Airbnb"),
    "snap":           ("company",     "Snap"),
    "twitter":        ("company",     "X (Twitter)"),
    "x":              ("company",     "X (Twitter)"),
    "spacex":         ("company",     "SpaceX"),
    "netflix":        ("company",     "Netflix"),
    "adobe":          ("company",     "Adobe"),
    "salesforce":     ("company",     "Salesforce"),
    "oracle":         ("company",     "Oracle"),
    "ibm":            ("company",     "IBM"),
    "huawei":         ("company",     "Huawei"),
    "alibaba":        ("company",     "Alibaba"),
    "tencent":        ("company",     "Tencent"),
    "anthropic":      ("company",     "Anthropic"),
    "deepmind":       ("company",     "DeepMind"),
    "palantir":       ("company",     "Palantir"),
    "snowflake":      ("company",     "Snowflake"),
    # Companies — Finance
    "jpmorgan":       ("company",     "JPMorgan"),
    "goldman":        ("company",     "Goldman Sachs"),
    "blackrock":      ("company",     "BlackRock"),
    "berkshire":      ("company",     "Berkshire Hathaway"),
    "citigroup":      ("company",     "Citigroup"),
    "hsbc":           ("company",     "HSBC"),
    # Companies — Energy
    "exxonmobil":     ("company",     "ExxonMobil"),
    "shell":          ("company",     "Shell"),
    "bp":             ("company",     "BP"),
    "chevron":        ("company",     "Chevron"),
    "aramco":         ("company",     "Saudi Aramco"),
    # Countries & regions
    "us":             ("country",     "United States"),
    "usa":            ("country",     "United States"),
    "america":        ("country",     "United States"),
    "american":       ("country",     "United States"),
    "china":          ("country",     "China"),
    "chinese":        ("country",     "China"),
    "russia":         ("country",     "Russia"),
    "russian":        ("country",     "Russia"),
    "uk":             ("country",     "United Kingdom"),
    "britain":        ("country",     "United Kingdom"),
    "british":        ("country",     "United Kingdom"),
    "eu":             ("country",     "European Union"),
    "europe":         ("country",     "European Union"),
    "european":       ("country",     "European Union"),
    "germany":        ("country",     "Germany"),
    "france":         ("country",     "France"),
    "japan":          ("country",     "Japan"),
    "japanese":       ("country",     "Japan"),
    "india":          ("country",     "India"),
    "taiwan":         ("country",     "Taiwan"),
    "ukraine":        ("country",     "Ukraine"),
    "israel":         ("country",     "Israel"),
    "iran":           ("country",     "Iran"),
    "saudi":          ("country",     "Saudi Arabia"),
    "korea":          ("country",     "South Korea"),
    "brazil":         ("country",     "Brazil"),
    "canada":         ("country",     "Canada"),
    "australia":      ("country",     "Australia"),
    # Institutions
    "fed":            ("institution", "Federal Reserve"),
    "federal reserve":("institution", "Federal Reserve"),
    "sec":            ("institution", "SEC"),
    "ftc":            ("institution", "FTC"),
    "fcc":            ("institution", "FCC"),
    "doj":            ("institution", "DOJ"),
    "ecb":            ("institution", "European Central Bank"),
    "imf":            ("institution", "IMF"),
    "nato":           ("institution", "NATO"),
    "who":            ("institution", "WHO"),
    "wto":            ("institution", "WTO"),
    "congress":       ("institution", "US Congress"),
    "senate":         ("institution", "US Senate"),
    "pentagon":       ("institution", "Pentagon"),
    "kremlin":        ("institution", "Kremlin"),
    "opec":           ("institution", "OPEC"),
    "un":             ("institution", "United Nations"),
    "world bank":     ("institution", "World Bank"),
}
