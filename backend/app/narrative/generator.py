"""Rule-based morning narrative script assembly."""

from __future__ import annotations

import re
from collections import defaultdict

from app.narrative.loader import RankedArticle, format_spoken_date, narrative_generated_at
from app.narrative.models import ArticleRef, NarrativeScript, NarrativeSection, SECTION_TITLES

WORDS_PER_MINUTE = 150
TARGET_MIN_WORDS = 300
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

WATCH_KEYWORDS = (
    "tomorrow",
    "next week",
    "hearing",
    "vote",
    "summit",
    "earnings",
    "deadline",
    "scheduled",
    "expected",
    "upcoming",
    "watch for",
    "set to",
)


def clean_for_speech(text: str) -> str:
    if not text:
        return ""
    text = URL_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def estimate_seconds(word_count: int) -> int:
    return max(1, int((word_count / WORDS_PER_MINUTE) * 60))


def _truncate(text: str, max_len: int) -> str:
    text = clean_for_speech(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _sentences(text: str, max_sentences: int = 2, max_len_per: int = 220) -> list[str]:
    text = clean_for_speech(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        out.append(_truncate(part, max_len_per))
        if len(out) >= max_sentences:
            break
    return out


def _first_sentence(text: str, max_len: int = 220) -> str:
    sentences = _sentences(text, 1, max_len)
    return sentences[0] if sentences else ""


def article_ref(article: RankedArticle) -> ArticleRef:
    return ArticleRef(
        topic=article.topic,
        topic_id=article.topic_id,
        report_id=article.report_id,
        article_title=article.title,
        source=article.source,
        article_url=article.url,
        article_id=article.article_id or None,
    )


def _finalize_sections(sections: list[NarrativeSection]) -> tuple[str, int]:
    script_text = "\n\n".join(s.text for s in sections)
    return script_text, count_words(script_text)


def _build_opening(report_date, topic_count: int, thread_hint: str, article_count: int) -> NarrativeSection:
    spoken_date = format_spoken_date(report_date)
    text = (
        f"Good morning. This is your WhatsNews morning intelligence briefing for {spoken_date}. "
        f"Across {topic_count} topics, {thread_hint} shaped today's landscape. "
        f"We distilled {article_count} of the strongest publishable stories into a single cross-topic listen "
        "so you can grasp the day in a few minutes without opening every section separately."
    )
    return NarrativeSection(
        id="opening",
        title=SECTION_TITLES["opening"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
    )


def _build_top_story(top: RankedArticle) -> NarrativeSection:
    summary_parts = _sentences(top.summary, 2, 240)
    wim = clean_for_speech(top.why_it_matters)
    source = clean_for_speech(top.source) or "our sources"

    parts = [
        f"The top story today comes from {top.topic}, reported by {source}.",
        clean_for_speech(top.title) + ".",
    ]
    parts.extend(summary_parts)
    if wim:
        parts.append(f"Why it matters: {wim}")
    parts.append(
        f"This lead item stands out in {top.topic} because it carries the strongest signal "
        "in today's ranked coverage and sets the tone for the rest of the briefing."
    )

    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="top_story",
        title=SECTION_TITLES["top_story"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=[article_ref(top)],
    )


def _build_key_developments(articles: list[RankedArticle]) -> NarrativeSection:
    parts: list[str] = [
        "Beyond the top story, here are the key developments worth your attention.",
        "These items round out the day across our tracked topics and add context you should not miss.",
    ]
    refs: list[ArticleRef] = []

    if not articles:
        parts.append(
            "Several additional developments rounded out the day across our tracked topics, "
            "even as the lead headline dominated attention."
        )
        text = clean_for_speech(" ".join(parts))
        return NarrativeSection(
            id="key_developments",
            title=SECTION_TITLES["key_developments"],
            text=text,
            estimated_seconds=estimate_seconds(count_words(text)),
        )

    by_topic: dict[str, list[RankedArticle]] = defaultdict(list)
    for article in articles:
        by_topic[article.topic].append(article)

    for topic, topic_articles in by_topic.items():
        parts.append(f"In {topic},")
        for article in topic_articles:
            title = clean_for_speech(article.title)
            summary_bits = _sentences(article.summary, 2, 180)
            source = clean_for_speech(article.source)
            lead = f"{title}."
            if summary_bits:
                lead += " " + " ".join(summary_bits)
            if source:
                lead += f" Source: {source}."
            parts.append(lead)
            refs.append(article_ref(article))

    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="key_developments",
        title=SECTION_TITLES["key_developments"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs,
    )


def _build_why_it_matters(articles: list[RankedArticle]) -> NarrativeSection:
    refs: list[ArticleRef] = []
    parts: list[str] = [
        "Why it matters:",
        "Taken together, today's coverage highlights several reasons these stories deserve attention "
        "beyond the headline cycle.",
    ]
    seen: set[str] = set()

    for article in articles:
        wim = clean_for_speech(article.why_it_matters)
        if not wim or wim in seen:
            continue
        seen.add(wim)
        parts.append(f"On {article.topic}: {wim}")
        refs.append(article_ref(article))

    if len(parts) <= 2:
        parts.append(
            "Together, these developments connect to broader shifts in policy, markets, and technology "
            "that will shape decisions in the weeks ahead."
        )
    else:
        parts.append(
            "These threads connect policy, markets, and geopolitics in ways that extend beyond any single headline."
        )

    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="why_it_matters",
        title=SECTION_TITLES["why_it_matters"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs,
    )


def _extract_watch_lines(articles: list[RankedArticle]) -> list[str]:
    lines: list[str] = []
    for article in articles:
        blob = f"{article.title} {article.summary} {article.why_it_matters}".lower()
        for kw in WATCH_KEYWORDS:
            if kw in blob:
                snippet = _first_sentence(article.summary, 140) or clean_for_speech(article.title)
                lines.append(f"In {article.topic}, watch for signals around {kw}: {snippet}")
                break
        if len(lines) >= 4:
            break
    return lines


def _build_what_to_watch(articles: list[RankedArticle]) -> NarrativeSection:
    watch_lines = _extract_watch_lines(articles)
    refs: list[ArticleRef] = []

    by_topic: dict[str, RankedArticle] = {}
    for article in articles:
        if article.topic not in by_topic:
            by_topic[article.topic] = article

    parts = [
        "What to watch next:",
        "Looking ahead, here is what to monitor across the topics in today's briefing.",
    ]

    for topic, article in by_topic.items():
        snippet = _first_sentence(article.summary, 150) or clean_for_speech(article.title)
        parts.append(
            f"For {topic}, monitor whether {snippet} gains follow-through in the days ahead."
        )
        refs.append(article_ref(article))

    for line in watch_lines[:3]:
        if line not in parts:
            parts.append(line)

    if len(parts) <= 2:
        parts.append(
            "Follow how leaders, markets, and institutions respond over the next few days. "
            "The follow-through often matters more than the initial announcement."
        )

    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="what_to_watch_next",
        title=SECTION_TITLES["what_to_watch_next"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs[:6],
    )


def _build_closing(report_date) -> NarrativeSection:
    spoken_date = format_spoken_date(report_date)
    text = (
        f"That is your morning briefing for {spoken_date}. "
        "Open WhatsNews to read the full stories, compare topics side by side, "
        "and review the Why It Matters context for each article in today's report."
    )
    return NarrativeSection(
        id="closing",
        title=SECTION_TITLES["closing"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
    )


def _thread_hint(articles: list[RankedArticle]) -> str:
    topics = list(dict.fromkeys(a.topic for a in articles[:8]))
    if len(topics) >= 3:
        return f"threads in {topics[0]}, {topics[1]}, and {topics[2]}"
    if len(topics) == 2:
        return f"movement in {topics[0]} and {topics[1]}"
    if topics:
        return f"developments in {topics[0]}"
    return "several important developments"


def _perspective_metadata(
    *,
    perspective_used: bool,
    perspective: dict | None = None,
    supporting_evidence_used_count: int = 0,
    fallback_reason: str | None = None,
) -> dict:
    meta = {
        "perspective_used": perspective_used,
        "perspective_id": perspective.get("id") if perspective else None,
        "supporting_evidence_used_count": supporting_evidence_used_count,
        "perspective_theme_count": len(perspective.get("themes") or []) if perspective else 0,
        "fallback_reason": fallback_reason,
    }
    if perspective_used and perspective:
        meta["perspective_headline"] = perspective.get("headline")
        meta["perspective_confidence"] = perspective.get("confidence")
    return meta


def _articles_by_id(articles: list[RankedArticle]) -> dict[int, RankedArticle]:
    return {a.article_id: a for a in articles if a.article_id}


def _match_supporting_articles(
    articles: list[RankedArticle],
    perspective: dict,
) -> list[RankedArticle]:
    by_id = _articles_by_id(articles)
    by_title = {(a.title, a.topic): a for a in articles}
    matched: list[RankedArticle] = []
    seen_ids: set[int] = set()

    for item in perspective.get("supporting_evidence") or []:
        article_id = item.get("article_id")
        if isinstance(article_id, int) and article_id in by_id:
            article = by_id[article_id]
        else:
            article = by_title.get((item.get("title"), item.get("topic")))
        if article is None or article.article_id in seen_ids:
            continue
        seen_ids.add(article.article_id)
        matched.append(article)

    return matched


def _reorder_articles(
    articles: list[RankedArticle],
    supporting: list[RankedArticle],
) -> list[RankedArticle]:
    supporting_ids = {a.article_id for a in supporting}
    rest = [a for a in articles if a.article_id not in supporting_ids]
    return supporting + rest


def _build_perspective_opening(
    report_date,
    topic_count: int,
    perspective: dict,
    article_count: int,
) -> NarrativeSection:
    spoken_date = format_spoken_date(report_date)
    headline = clean_for_speech(perspective.get("headline") or "")
    themes = perspective.get("themes") or []
    theme_hint = themes[0] if themes else "today's cross-topic coverage"

    text = (
        f"Good morning. This is your WhatsNews morning intelligence briefing for {spoken_date}. "
        f"Today's editorial read: {headline}. "
        f"Across {topic_count} topics, the through-line is {theme_hint.lower()}, "
        f"drawn from {article_count} of the strongest publishable stories in today's report."
    )
    return NarrativeSection(
        id="opening",
        title=SECTION_TITLES["opening"],
        text=clean_for_speech(text),
        estimated_seconds=estimate_seconds(count_words(text)),
    )


def _build_perspective_top_story(
    perspective: dict,
    lead: RankedArticle | None,
) -> NarrativeSection:
    perspective_text = clean_for_speech(perspective.get("perspective") or "")
    body_sentences = _sentences(perspective_text, 3, 260)
    parts = [
        "Today's editorial perspective:",
        body_sentences[0] if body_sentences else perspective_text,
    ]
    if len(body_sentences) > 1:
        parts.append(body_sentences[1])

    if lead:
        source = clean_for_speech(lead.source) or "our sources"
        parts.append(
            f"The strongest signal behind this read comes from {lead.topic}, "
            f"reported by {source}: {clean_for_speech(lead.title)}."
        )

    text = clean_for_speech(" ".join(parts))
    refs = [article_ref(lead)] if lead else []
    return NarrativeSection(
        id="top_story",
        title=SECTION_TITLES["top_story"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs,
    )


def _build_perspective_key_developments(
    supporting: list[RankedArticle],
    perspective: dict,
    remaining: list[RankedArticle],
) -> NarrativeSection:
    evidence_map = {
        item.get("article_id"): item
        for item in (perspective.get("supporting_evidence") or [])
        if item.get("article_id") is not None
    }
    parts = [
        "Here is the evidence behind today's editorial judgment.",
        "These are the key stories that anchor the perspective, followed by other developments across the briefing.",
    ]
    refs: list[ArticleRef] = []

    for article in supporting:
        evidence = evidence_map.get(article.article_id) or {}
        reason = clean_for_speech(evidence.get("reason") or "")
        summary_bits = _sentences(article.summary, 1, 180)
        chunk = f"In {article.topic}, {clean_for_speech(article.title)}."
        if summary_bits:
            chunk += " " + summary_bits[0]
        if reason:
            chunk += f" Editorial read: {reason}"
        parts.append(chunk)
        refs.append(article_ref(article))

    by_topic: dict[str, list[RankedArticle]] = defaultdict(list)
    for article in remaining[:6]:
        by_topic[article.topic].append(article)

    if by_topic:
        parts.append("Other topic developments today include the following.")
        for topic, topic_articles in by_topic.items():
            parts.append(f"In {topic},")
            for article in topic_articles[:2]:
                title = clean_for_speech(article.title)
                summary_bits = _sentences(article.summary, 1, 160)
                lead = f"{title}."
                if summary_bits:
                    lead += " " + summary_bits[0]
                parts.append(lead)
                refs.append(article_ref(article))

    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="key_developments",
        title=SECTION_TITLES["key_developments"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs,
    )


def _build_perspective_why_it_matters(
    supporting: list[RankedArticle],
    perspective: dict,
) -> NarrativeSection:
    themes = perspective.get("themes") or []
    theme_phrase = ", ".join(themes[:3]).lower() if themes else "today's connected coverage"
    parts = [
        "Why it matters:",
        f"Taken together, the pattern around {theme_phrase} matters because it shapes decisions "
        "that extend beyond any single headline cycle.",
    ]
    refs: list[ArticleRef] = []
    seen: set[str] = set()

    for article in supporting[:4]:
        wim = clean_for_speech(article.why_it_matters)
        if not wim or wim in seen:
            continue
        seen.add(wim)
        parts.append(f"From {article.topic}: {_first_sentence(wim, 220)}")
        refs.append(article_ref(article))

    parts.append(
        "The editorial implication is that operators should read these moves as connected signals, "
        "not isolated updates."
    )
    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="why_it_matters",
        title=SECTION_TITLES["why_it_matters"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs,
    )


def _build_perspective_what_to_watch(perspective: dict, supporting: list[RankedArticle]) -> NarrativeSection:
    watch_items = [
        clean_for_speech(item)
        for item in (perspective.get("watch_next") or [])
        if clean_for_speech(item)
    ]
    parts = [
        "What to watch next:",
        "Based on today's editorial perspective, monitor the following.",
    ]
    refs: list[ArticleRef] = []
    for item in watch_items[:4]:
        parts.append(item)

    for article in supporting[:3]:
        refs.append(article_ref(article))

    if len(parts) <= 2:
        parts.extend(_extract_watch_lines(supporting)[:2])

    text = clean_for_speech(" ".join(parts))
    return NarrativeSection(
        id="what_to_watch_next",
        title=SECTION_TITLES["what_to_watch_next"],
        text=text,
        estimated_seconds=estimate_seconds(count_words(text)),
        article_refs=refs,
    )


def _build_perspective_closing(report_date, perspective: dict) -> NarrativeSection:
    spoken_date = format_spoken_date(report_date)
    headline = clean_for_speech(perspective.get("headline") or "today's briefing")
    text = (
        f"That is your morning briefing for {spoken_date}. "
        f"The editorial through-line was {headline.rstrip('.')}. "
        "Open WhatsNews to read the full stories and compare topics side by side."
    )
    return NarrativeSection(
        id="closing",
        title=SECTION_TITLES["closing"],
        text=clean_for_speech(text),
        estimated_seconds=estimate_seconds(count_words(text)),
    )


def _build_perspective_aware_script(
    report_date,
    articles: list[RankedArticle],
    source_report_ids: list[int],
    topic_count: int,
    perspective: dict,
) -> NarrativeScript:
    supporting = _match_supporting_articles(articles, perspective)
    if not supporting:
        supporting = articles[: min(5, len(articles))]

    ordered = _reorder_articles(articles, supporting)
    lead = supporting[0] if supporting else articles[0]
    remaining = [a for a in ordered if a.article_id != lead.article_id]

    sections = [
        _build_perspective_opening(report_date, topic_count, perspective, len(articles)),
        _build_perspective_top_story(perspective, lead),
        _build_perspective_key_developments(supporting, perspective, remaining),
        _build_perspective_why_it_matters(supporting, perspective),
        _build_perspective_what_to_watch(perspective, supporting),
        _build_perspective_closing(report_date, perspective),
    ]

    _expand_key_developments_if_needed(sections, ordered)

    script_text, word_count = _finalize_sections(sections)
    all_refs: list[ArticleRef] = []
    for section in sections:
        all_refs.extend(section.article_refs)

    for section in sections:
        section.estimated_seconds = estimate_seconds(count_words(section.text))

    script = NarrativeScript(
        report_date=str(report_date),
        scope="daily",
        status="pending",
        version=1,
        generated_at=narrative_generated_at(),
        generation_method="rule_v1+perspective",
        word_count=word_count,
        estimated_duration_seconds=estimate_seconds(word_count),
        script_text=script_text,
        sections=sections,
        source_report_ids=source_report_ids,
        article_refs=all_refs,
        metadata=_perspective_metadata(
            perspective_used=True,
            perspective=perspective,
            supporting_evidence_used_count=len(supporting),
        ),
    )
    return script


def _build_legacy_script(
    report_date,
    articles: list[RankedArticle],
    source_report_ids: list[int],
    topic_count: int,
    *,
    fallback_reason: str | None = None,
) -> NarrativeScript:
    top = articles[0]
    rest = articles[1:]

    sections = [
        _build_opening(report_date, topic_count, _thread_hint(articles), len(articles)),
        _build_top_story(top),
        _build_key_developments(rest),
        _build_why_it_matters(articles),
        _build_what_to_watch(articles),
        _build_closing(report_date),
    ]

    _expand_key_developments_if_needed(sections, articles)

    script_text, word_count = _finalize_sections(sections)
    all_refs: list[ArticleRef] = []
    for section in sections:
        all_refs.extend(section.article_refs)

    for section in sections:
        section.estimated_seconds = estimate_seconds(count_words(section.text))

    return NarrativeScript(
        report_date=str(report_date),
        scope="daily",
        status="pending",
        version=1,
        generated_at=narrative_generated_at(),
        generation_method="rule_v1",
        word_count=word_count,
        estimated_duration_seconds=estimate_seconds(word_count),
        script_text=script_text,
        sections=sections,
        source_report_ids=source_report_ids,
        article_refs=all_refs,
        metadata=_perspective_metadata(
            perspective_used=False,
            fallback_reason=fallback_reason,
        ),
    )


def _expand_key_developments_if_needed(
    sections: list[NarrativeSection],
    articles: list[RankedArticle],
) -> None:
    """Grounded expansion when the rule-based script is still below minimum length."""
    script_text, word_count = _finalize_sections(sections)
    if word_count >= TARGET_MIN_WORDS:
        return

    key_section = next(s for s in sections if s.id == "key_developments")
    extra_parts: list[str] = [
        "To round out today's picture, here is additional context from the remaining coverage.",
    ]
    existing_titles = {r.article_title for r in key_section.article_refs}

    for article in articles:
        if article.title in existing_titles:
            continue
        summary_bits = _sentences(article.summary, 2, 200)
        wim = clean_for_speech(article.why_it_matters)
        chunk = f"Also in {article.topic}: {clean_for_speech(article.title)}."
        if summary_bits:
            chunk += " " + " ".join(summary_bits)
        if wim:
            chunk += f" Why it matters: {wim}"
        extra_parts.append(chunk)
        key_section.article_refs.append(article_ref(article))
        _, word_count = _finalize_sections(sections)
        if word_count >= TARGET_MIN_WORDS:
            break

    if len(extra_parts) > 1:
        key_section.text = clean_for_speech(key_section.text + " " + " ".join(extra_parts[1:]))
        key_section.estimated_seconds = estimate_seconds(count_words(key_section.text))


def build_rule_based_script(
    report_date,
    articles: list[RankedArticle],
    source_report_ids: list[int],
    topic_count: int,
    perspective: dict | None = None,
) -> NarrativeScript:
    if not articles:
        raise ValueError("No articles available for narrative generation.")

    if perspective and perspective.get("status") == "ready":
        headline = (perspective.get("headline") or "").strip()
        body = (perspective.get("perspective") or "").strip()
        if headline and body:
            return _build_perspective_aware_script(
                report_date,
                articles,
                source_report_ids,
                topic_count,
                perspective,
            )
        return _build_legacy_script(
            report_date,
            articles,
            source_report_ids,
            topic_count,
            fallback_reason="perspective_incomplete",
        )

    fallback_reason = "no_ready_perspective" if perspective is None else "perspective_not_ready"
    return _build_legacy_script(
        report_date,
        articles,
        source_report_ids,
        topic_count,
        fallback_reason=fallback_reason,
    )
