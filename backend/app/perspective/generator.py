"""Rule-based daily editorial perspective generation (Phase 17.3)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from app.editorial.bridges import CROSS_TOPIC_BRIDGES
from app.perspective.models import EditorialPerspective, PerspectiveArticle

IMPACT_THEME_LABELS: dict[str, str] = {
    "technology": "technology and infrastructure capacity",
    "market": "market repricing and capital allocation",
    "policy": "policy and regulatory enforcement",
    "regulation": "compliance and rulemaking",
    "business": "corporate strategy and competitive response",
    "geopolitics": "geopolitical leverage and alliance dynamics",
    "defense": "defense procurement and security posture",
    "healthcare": "healthcare access and clinical adoption",
    "energy": "energy supply, pricing, and transition risk",
    "consumer": "consumer adoption and product behavior",
}


def _detect_dominant_bridge(articles: list[PerspectiveArticle]) -> tuple[str | None, int]:
    """Return (bridge label, article count) for the strongest cross-topic thread."""
    bridge_counts: Counter[str] = Counter()
    for article in articles:
        for label in article.cross_topic_candidates:
            bridge_counts[label] += 1
    if not bridge_counts:
        return None, 0
    label, count = bridge_counts.most_common(1)[0]
    return label, count


def _detect_themes(articles: list[PerspectiveArticle], bridge_label: str | None) -> list[str]:
    themes: list[str] = []
    if bridge_label:
        themes.append(bridge_label)

    tag_counter: Counter[str] = Counter()
    impact_counter: Counter[str] = Counter()
    for article in articles[:8]:
        for tag in article.editorial_tags:
            tag_counter[tag] += 1
        for impact in article.impact_types:
            impact_counter[impact] += 1

    for tag, _ in tag_counter.most_common(3):
        if tag not in themes:
            themes.append(tag)
    for impact, _ in impact_counter.most_common(2):
        label = IMPACT_THEME_LABELS.get(impact, impact.replace("_", " "))
        if label not in themes:
            themes.append(label)
        if len(themes) >= 4:
            break

    return themes[:4]


def _evidence_reason(article: PerspectiveArticle) -> str:
    if article.impact_types:
        primary = article.impact_types[0]
        mechanism = IMPACT_THEME_LABELS.get(primary, primary)
        return f"Connects to {mechanism} through today's {article.topic} coverage."
    return f"Anchors the pattern in {article.topic} with a high-signal development."


def _select_supporting(articles: list[PerspectiveArticle]) -> list[PerspectiveArticle]:
    if not articles:
        return []
    selected: list[PerspectiveArticle] = []
    topics_seen: set[str] = set()

    for article in articles:
        if len(selected) >= 5:
            break
        selected.append(article)
        topics_seen.add(article.topic)

    for article in articles:
        if len(selected) >= 5:
            break
        if article in selected:
            continue
        if article.topic not in topics_seen and len(selected) < 5:
            selected.append(article)
            topics_seen.add(article.topic)

    return selected[:5]


def _build_headline(
    bridge_label: str | None,
    themes: list[str],
    top_impact: str | None,
) -> str:
    if bridge_label:
        short = bridge_label.split(" and ")[0]
        headline = f"Today's briefing centers on {short.lower()}"
    elif themes:
        headline = f"Today's pattern: {themes[0].lower()}"
    elif top_impact:
        headline = f"{top_impact.capitalize()} drives today's cross-topic signal"
    else:
        headline = "Today's developments point to a connected operational shift"

    words = headline.split()
    if len(words) > 16:
        headline = " ".join(words[:16])
    while len(headline.split()) < 8:
        headline += " across multiple sectors"
    return headline[0].upper() + headline[1:] if headline else headline


def _topic_list(topics: list[str]) -> str:
    uniq = list(dict.fromkeys(topics))
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) == 2:
        return f"{uniq[0]} and {uniq[1]}"
    return ", ".join(uniq[:-1]) + f", and {uniq[-1]}"


def _build_perspective_text(
    *,
    bridge_label: str | None,
    themes: list[str],
    supporting: list[PerspectiveArticle],
    top_impact: str | None,
) -> str:
    topics = [a.topic for a in supporting]
    topic_phrase = _topic_list(topics)
    lead_article = supporting[0]

    if bridge_label:
        pattern = (
            f"Today's most important pattern is not a single headline but a thread running "
            f"through {topic_phrase}: {bridge_label.lower()}."
        )
    elif top_impact:
        pattern = (
            f"Across {topic_phrase}, the through-line is {IMPACT_THEME_LABELS.get(top_impact, top_impact)} "
            f"rather than isolated announcements."
        )
    else:
        pattern = (
            f"Taken together, coverage in {topic_phrase} points to a shared operational shift "
            f"that matters more than any one story alone."
        )

    why = (
        "That matters because decision-makers are adjusting plans based on second-order effects — "
        "supply constraints, policy timing, and competitive response — not just today's headlines."
    )

    evidence_bits = []
    for article in supporting[:3]:
        snippet = article.why_it_matters.split(".")[0].strip()
        if snippet:
            evidence_bits.append(f"In {article.topic}, {snippet.lower()}.")

    evidence = " ".join(evidence_bits) if evidence_bits else (
        f"The signal is reinforced by {lead_article.topic} coverage of "
        f"\"{lead_article.title[:80]}\" and parallel developments elsewhere."
    )

    closing = (
        "The editorial read is that operators should track whether these threads converge "
        "into policy action, market repricing, or deployment delays over the next few days."
    )

    text = f"{pattern} {why} {evidence} {closing}"
    words = text.split()
    if len(words) > 220:
        text = " ".join(words[:220])
    return text


def _collect_watch_next(supporting: list[PerspectiveArticle]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for article in supporting:
        watch = (article.watch_next or "").strip()
        if not watch:
            continue
        key = watch.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(watch)
        if len(items) >= 4:
            break

    if len(items) < 2:
        defaults = [
            "Watch whether follow-on statements clarify scope and timing.",
            "Monitor whether markets or regulators respond within the next session.",
        ]
        for item in defaults:
            if len(items) >= 4:
                break
            if item.lower() not in seen:
                items.append(item)
                seen.add(item.lower())
    return items[:4]


def _compute_confidence(
    supporting: list[PerspectiveArticle],
    bridge_count: int,
) -> str:
    topics = len({a.topic for a in supporting})
    if len(supporting) >= 4 and topics >= 3 and bridge_count >= 2:
        return "high"
    if len(supporting) >= 3 and topics >= 2:
        return "medium"
    return "low"


def build_rule_based_perspective(
    report_date,
    articles: list[PerspectiveArticle],
) -> EditorialPerspective:
    """Generate a grounded editorial perspective from today's articles."""
    supporting = _select_supporting(articles)
    bridge_label, bridge_count = _detect_dominant_bridge(articles)
    themes = _detect_themes(supporting, bridge_label)

    impact_counter: Counter[str] = Counter()
    for article in supporting:
        for impact in article.impact_types:
            impact_counter[impact] += 1
    top_impact = impact_counter.most_common(1)[0][0] if impact_counter else None

    headline = _build_headline(bridge_label, themes, top_impact)
    perspective = _build_perspective_text(
        bridge_label=bridge_label,
        themes=themes,
        supporting=supporting,
        top_impact=top_impact,
    )
    watch_next = _collect_watch_next(supporting)
    confidence = _compute_confidence(supporting, bridge_count)

    supporting_evidence = [
        {
            "article_id": article.article_id,
            "topic": article.topic,
            "title": article.title,
            "reason": _evidence_reason(article),
        }
        for article in supporting
    ]

    return EditorialPerspective(
        report_date=report_date,
        status="pending",
        headline=headline,
        perspective=perspective,
        supporting_evidence=supporting_evidence,
        watch_next=watch_next,
        confidence=confidence,
        themes=themes,
        generated_at=datetime.now(tz=ZoneInfo("UTC")).isoformat(),
        generation_method="rule_v1",
    )


def detect_active_bridges(articles: list[PerspectiveArticle]) -> list[str]:
    """Return bridge labels with articles in at least two topics (for diagnostics)."""
    active: list[str] = []
    for bridge in CROSS_TOPIC_BRIDGES:
        matching_topics: set[str] = set()
        for article in articles:
            text = (article.title + " " + article.summary).lower()
            if any(kw in text for kw in bridge["keywords"]):
                matching_topics.add(article.topic)
        if len(matching_topics) >= 2:
            active.append(bridge["label"])
    return active
