"""Rule-based why_it_matters generation (deterministic templates)."""

import hashlib

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "regulation": [
        "legislation", "regulation", "law", "passes", "ban", "rules",
        "liability", "government", "summit", "policy", "compliance",
        "directive", "mandate", "executive order", "enforce",
    ],
    "product": [
        "launches", "releases", "announces", "unveils", "introduces",
        "new product", "new tool", "new feature", "now available",
        "rolls out", "ships", "debuts", "open-source", "open source",
    ],
    "research": [
        "research", "advances", "breakthrough", "study", "discovery",
        "scientists", "record", "progress", "new model", "paper",
        "published", "findings", "experiment",
    ],
    "adoption": [
        "adoption", "developers", "users", "majority", "mainstream",
        "growth", "survey", "market share", "deployed", "rollout",
        "integration", "workforce", "enterprise",
    ],
    "funding": [
        "funding", "raises", "secures", "investment", "valuation",
        "acquisition", "ipo", "venture", "series", "billion",
        "million", "deal", "merger",
    ],
    "incident": [
        "breach", "hack", "leak", "failure", "outage", "bias",
        "lawsuit", "controversy", "recall", "accident", "risk",
        "vulnerability", "misuse", "warning",
    ],
}

CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "regulation": [
        "Regulators drew a new line in {topic}. The compliance burden alone will force smaller players to consolidate or exit.",
        "A binding policy shift for {topic}. This doesn't just constrain incumbents — it defines which business models are viable going forward.",
        "Governance in {topic} moved from discussion to enforcement. Companies that built without anticipating this are now carrying regulatory debt.",
        "New rules redefine what's legal in {topic}. The second-order effect: insurance, liability, and procurement standards all get rewritten downstream.",
    ],
    "product": [
        "A new {topic} product entered the market. The real signal is the pricing and distribution strategy that forces competitors to respond.",
        "This release shifts the baseline in {topic}. Features that were differentiators last quarter are now table stakes.",
        "A competitive move in {topic} targeting distribution over performance. Market share in this cycle goes to whoever reduces adoption friction fastest.",
    ],
    "research": [
        "A technical boundary in {topic} just moved. The practical question is whether the cost of deploying this drops fast enough to matter.",
        "New research narrows the gap between lab results and production systems in {topic}. The bottleneck shifts from capability to engineering and governance.",
        "A breakthrough on paper in {topic}. History says the real impact arrives 18\u201336 months later, when the tooling catches up.",
    ],
    "adoption": [
        "{topic} crossed from pilot to production at scale. The failure modes now are organizational, not technical.",
        "Usage of {topic} passed a deployment threshold. Accountability and audit requirements grow exponentially from here.",
        "Mainstream {topic} adoption accelerated. The infrastructure and governance built for small-scale usage will start breaking under load.",
    ],
    "funding": [
        "Capital concentrated into a specific layer of {topic}. Where investors place bets at this scale, the supply chain reshapes around them.",
        "A major funding event in {topic} shifts the power balance between incumbents and challengers. Execution speed, not idea quality, decides the winner.",
        "Money flowed into {topic} at a pace that signals conviction, not speculation. Talent, tooling, and partnerships all follow the capital downstream.",
    ],
    "incident": [
        "A {topic} system failed in production with real-world consequences. The regulatory and procurement response will move faster than the technical fix.",
        "{topic} risk surfaced at a scale that can't be written off as an edge case. The trust deficit this creates takes years to reverse.",
        "An operational failure in {topic} exposed gaps that audits missed. The second-order effect is tighter procurement standards across the entire sector.",
    ],
    "fallback": [
        "A development in {topic} that looks incremental on the surface. The structural significance becomes clear when you follow who's responding and how fast.",
        "A signal in {topic} worth reading past the headline. Small shifts accumulating is how landscapes change before anyone labels it a trend.",
        "Movement in {topic} that doesn't fit the usual categories. These are often the developments that redefine the categories themselves.",
    ],
}

TOPIC_SPECIFIC_TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("Artificial Intelligence", "regulation"): [
        "AI governance shifted from voluntary to mandatory. The architectures and training practices that don't meet the new bar face deployment bans, not fines.",
        "Regulators defined what's acceptable in AI. This forces product roadmap changes within quarters, not years \u2014 compliance is now a shipping blocker.",
    ],
    ("Artificial Intelligence", "research"): [
        "A capability frontier in AI expanded. The real race starts now: who can move this from benchmark to reliable production system at acceptable cost.",
        "AI research hit a new mark. The bottleneck isn't intelligence \u2014 it's inference cost, data rights, and organizational readiness to deploy responsibly.",
    ],
    ("Artificial Intelligence", "adoption"): [
        "AI moved deeper into operational workflows. The accountability gap between what the system decides and who answers for it is now the critical risk.",
        "Enterprise AI crossed from experiment to dependency. The hard problem shifted from 'does it work' to 'what happens when it doesn't.'",
    ],
    ("Climate Change", "regulation"): [
        "Climate policy moved from target-setting to enforcement. The capital reallocation this triggers is measured in trillions, not billions.",
        "A binding climate mandate landed. The gap between pledging net-zero and funding the infrastructure to get there just became a legal obligation.",
    ],
    ("Climate Change", "incident"): [
        "A physical climate event exceeded planning assumptions. Insurance models, infrastructure budgets, and migration patterns all recalibrate from here.",
        "Climate risk materialized at a scale that invalidates previous actuarial models. The adaptation investment gap just became politically impossible to ignore.",
    ],
    ("Climate Change", "funding"): [
        "Clean-energy capital deployed at scale, not pledged. The transition moved from policy aspiration to bankable infrastructure.",
        "Climate finance concentrated in deployment over research. The money is following proven technology to scale, not betting on breakthroughs.",
    ],
}


def _detect_category(text: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "fallback"


def _pick_variant(variants: list[str], title: str) -> str:
    idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(variants)
    return variants[idx]


def generate_why_it_matters(title: str, summary: str, topic: str) -> str:
    text = (title + " " + summary).lower()
    category = _detect_category(text)

    templates = list(CATEGORY_TEMPLATES[category])
    topic_extras = TOPIC_SPECIFIC_TEMPLATES.get((topic, category), [])
    all_templates = topic_extras + templates

    template = _pick_variant(all_templates, title)
    return template.format(topic=topic)
