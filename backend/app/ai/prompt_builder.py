"""Centralized prompt construction for the AI Intelligence Platform.

Phase 23: the Prompt Builder accepts a fully-built ContextObject and ONLY
formats it into LLM messages. It NEVER fetches data — all data sourcing happens
in the Context Builder. This keeps prompt logic pure and testable.

Responsibilities:
  - system prompt
  - context injection (article + topic + cross-topic + temporal)
  - instruction alignment per AI_MODE
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.schemas import AIMode, ArticleContext, ChatMessage

if TYPE_CHECKING:
    from app.ai.context_builder import ContextObject


# ─── Grounding system prompt ──────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are WhatsNews AI, an intelligence assistant embedded in a daily news briefing app.

Your role is to surface what actually matters about news events and help readers
think clearly about what they're reading. You are a research intelligence system —
you reason across multiple articles, topics, and time, not just a single headline.

Rules you must always follow:
1. Ground ALL responses in the article and context provided. Do not invent facts.
2. When you are uncertain, say so explicitly. Label analysis as "Analysis:" not fact.
3. Separate what happened (fact) from what it might mean (analysis).
4. Be crisp. Readers are busy. No unnecessary filler.
5. Never hallucinate sources, quotes, or statistics not in the provided context.
6. When related articles or cross-topic links are provided, USE them to compare,
   connect, and contextualize — that is your advantage over a generic chatbot.
7. If the user asks about something outside the provided context, you may answer
   generally but must clearly state you are going beyond the provided material.

Tone: authoritative, clear, direct. Not casual. Not breathless. Journalist-grade.
"""

_QUESTIONS_SUFFIX = """\

At the end, on a new line write EXACTLY this marker:
---QUESTIONS---
Then list 5 follow-up questions a reader might want to ask, one per line,
starting with a dash (-). Make them specific to this article and topic.
Questions should vary in angle: one beginner, one expert, one investment,
one geopolitical or social, one forward-looking.
Example:
---QUESTIONS---
- What does this mean for everyday consumers?
- How does this compare to previous policy cycles?
- What is the investment risk profile here?
- Which countries or regions are most exposed?
- What would need to happen for this trend to reverse?
"""


# ─── Context block formatters ─────────────────────────────────────────────────

def _format_article(article: ArticleContext, date_str: str | None) -> str:
    parts = ["[CURRENT ARTICLE]"]
    parts.append(f"Title: {article.title}")
    if article.source:
        parts.append(f"Source: {article.source}")
    if article.topic:
        parts.append(f"Topic: {article.topic}")
    if date_str:
        parts.append(f"Date: {date_str}")
    if article.summary:
        parts.append(f"Summary: {article.summary}")
    if article.why_it_matters:
        parts.append(f"Why It Matters (editorial): {article.why_it_matters}")
    if article.url:
        parts.append(f"URL: {article.url}")
    return "\n".join(parts)


def _format_topic_context(context: "ContextObject") -> str:
    tc = context.topic_context
    if not tc.recent_articles:
        return ""
    lines = [f"\n[RELATED ARTICLES IN {tc.name.upper()}] ({tc.article_count} recent)"]
    for i, ra in enumerate(tc.recent_articles, start=1):
        bits = [f"{i}. {ra.title}"]
        if ra.source:
            bits.append(f"({ra.source})")
        lines.append(" ".join(bits))
        if ra.why_it_matters:
            lines.append(f"   Why it matters: {ra.why_it_matters}")
    return "\n".join(lines)


def _format_cross_topic_context(context: "ContextObject") -> str:
    links = context.cross_topic_context.links
    if not links:
        return ""
    lines = ["\n[CROSS-TOPIC LINKS]"]
    lines.append(
        "This article connects to other topics. Use these to broaden your analysis:"
    )
    for lnk in links:
        lines.append(f"- {lnk.topic}: {lnk.reason}")
    return "\n".join(lines)


def _format_global_context(context: "ContextObject") -> str:
    """
    Phase 23D: inject global influence graph snapshot into the prompt.

    Included only when the graph has nodes (empty on first request, fills over time).
    Capped at 5 top nodes + 10 recent edges to stay within token budget.
    """
    gg = context.global_graph
    if not gg:
        return ""
    top_nodes = gg.get("top_nodes", [])
    edges = gg.get("edges", [])
    if not top_nodes:
        return ""

    lines = ["\n[GLOBAL MARKET GRAPH]"]
    lines.append("\nTop Influencers:")
    for n in top_nodes[:5]:
        sentiment_label = (
            "bullish" if n.get("sentiment", 0) > 0.2
            else "bearish" if n.get("sentiment", 0) < -0.2
            else "neutral"
        )
        # topics is a set in the node; convert to sorted list for display
        topics_list = sorted(n.get("topics", set()))[:3]
        topics_str = ", ".join(topics_list)
        lines.append(
            f"- {n['name'].upper()}: score={n.get('global_score', 0):.2f}"
            f"  sentiment={sentiment_label}"
            f"  topics=[{topics_str}]"
        )

    if edges:
        lines.append("\nRecent Relationships:")
        for e in edges[-10:]:
            lines.append(
                f"- {e['source']!r} →[{e['type']}]→ {e['target']}"
                f"  weight={e['weight']:.2f}"
            )

    return "\n".join(lines)


def _format_temporal_context(context: "ContextObject") -> str:
    tc = context.temporal_context
    if not tc.today_snapshots and not tc.prev_day_snapshots:
        return ""
    lines = ["\n[TODAY'S BRIEFING LANDSCAPE]"]
    if tc.today_snapshots:
        lines.append(f"Top stories across topics on {tc.today_date}:")
        for snap in tc.today_snapshots[:8]:
            lines.append(f"- {snap.topic}: {snap.top_story_title}")
    if tc.prev_day_snapshots:
        lines.append(f"\nFor trend comparison — top stories on {tc.prev_day_date}:")
        for snap in tc.prev_day_snapshots[:8]:
            lines.append(f"- {snap.topic}: {snap.top_story_title}")
    return "\n".join(lines)


def _build_full_context_block(
    context: "ContextObject",
    date_str: str | None,
    *,
    include_temporal: bool = True,
) -> str:
    blocks = [_format_article(context.article_context, date_str)]
    topic_block = _format_topic_context(context)
    if topic_block:
        blocks.append(topic_block)
    cross_block = _format_cross_topic_context(context)
    if cross_block:
        blocks.append(cross_block)
    global_block = _format_global_context(context)
    if global_block:
        blocks.append(global_block)
    if include_temporal:
        temporal_block = _format_temporal_context(context)
        if temporal_block:
            blocks.append(temporal_block)
    return "\n".join(blocks)


# ─── Per-mode instructions ────────────────────────────────────────────────────

_MODE_INSTRUCTIONS: dict[AIMode, str] = {
    AIMode.ARTICLE_INSIGHT: (
        "Generate 'Today's Insight' for the current article.\n\n"
        "Structure your response in exactly 3 sections:\n"
        "**What happened** — 1-2 sentences summarizing the core development.\n"
        "**Why it matters** — 2-3 sentences on significance and implications.\n"
        "**What to watch** — 1-2 sentences on the next development to follow.\n\n"
        "Keep the total response under 220 words. Be specific, not generic. "
        "If related articles are provided, weave in one comparative observation."
    ),
    AIMode.CROSS_TOPIC_ANALYSIS: (
        "Analyze how this article connects across topics.\n\n"
        "Using the cross-topic links provided, explain in 3 short sections:\n"
        "**Core event** — what happened.\n"
        "**Cross-topic ripple** — how it touches each linked topic and why.\n"
        "**Synthesis** — the bigger picture connecting these threads.\n\n"
        "Ground every connection in the provided context. Keep under 250 words."
    ),
    AIMode.BRIEFING_ANALYSIS: (
        "Analyze today's briefing landscape, not just this single article.\n\n"
        "Using the top stories across topics provided:\n"
        "**Theme of the day** — the dominant thread connecting today's stories.\n"
        "**Standouts** — 2-3 stories that matter most and why.\n"
        "**Watch list** — what to track going forward.\n\n"
        "Keep under 250 words. Reference specific stories from the landscape."
    ),
    AIMode.TREND_DETECTION: (
        "Detect patterns by comparing today's stories with the previous day.\n\n"
        "**Continuing threads** — stories developing across both days.\n"
        "**New signals** — what emerged that wasn't present before.\n"
        "**Trajectory** — where these trends appear to be heading.\n\n"
        "Be explicit about uncertainty. If data is thin, say so. Under 230 words."
    ),
    AIMode.SIMPLE_QA: (
        "Answer the user's question directly and concisely, grounded in the "
        "provided context. No preamble. If the answer isn't in the context, "
        "say what you can infer and flag the uncertainty."
    ),
}

_DEFAULT_INSTRUCTION = _MODE_INSTRUCTIONS[AIMode.ARTICLE_INSIGHT]


def _instruction_for(mode: AIMode) -> str:
    return _MODE_INSTRUCTIONS.get(mode, _DEFAULT_INSTRUCTION)


# ─── Public builders ──────────────────────────────────────────────────────────

def build_insight_prompt(
    context: "ContextObject",
    mode: AIMode = AIMode.ARTICLE_INSIGHT,
    date_str: str | None = None,
) -> list[dict[str, str]]:
    """
    Messages for the proactive initial generation (no user question yet).

    The instruction is mode-aware; temporal context is included for the
    briefing/trend modes that need it.
    """
    include_temporal = mode in (
        AIMode.BRIEFING_ANALYSIS,
        AIMode.TREND_DETECTION,
        AIMode.CROSS_TOPIC_ANALYSIS,
    )
    context_block = _build_full_context_block(
        context, date_str, include_temporal=include_temporal
    )
    instruction = _instruction_for(mode)

    user_message = f"{context_block}\n\n{instruction}{_QUESTIONS_SUFFIX}"
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


_TRANSLATION_SYSTEM_PROMPT = """\
You are a professional news translator. Translate the article provided into the
requested target language. Preserve meaning, tone, named entities, and numbers
precisely. Output ONLY the translated text: the translated title on the first line,
then one blank line, then the translated body. Do not add commentary, opinions,
analysis, or a "why it matters" section. Do not wrap the output in quotes or
markdown headers. Do not translate proper nouns that are commonly kept in their
original form (e.g. company and product names) unless a standard localized form exists.
"""


def build_translation_prompt(
    article: ArticleContext,
    target_language: str,
) -> list[dict[str, str]]:
    """
    Messages for AIMode.TRANSLATION (Phase 32, added 2026-07-05).

    Deliberately does NOT go through _build_full_context_block — related
    articles, cross-topic links, and the global graph are irrelevant noise
    for a pure translation task and risk the model commenting on them instead
    of just translating. Uses body_text when available (full article text),
    falling back to summary/why_it_matters for articles ingested before that
    field existed.
    """
    body = article.body_text or article.summary or article.why_it_matters or ""
    user_message = (
        f"Target language: {target_language}\n\n"
        f"Title: {article.title}\n\n"
        f"Body:\n{body}"
    )
    return [
        {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def build_chat_prompt(
    context: "ContextObject",
    history: list[ChatMessage],
    user_question: str,
    mode: AIMode = AIMode.ARTICLE_INSIGHT,
    date_str: str | None = None,
) -> list[dict[str, str]]:
    """
    Messages for a follow-up conversation turn.

    Context is re-injected as the first user message so the model stays
    grounded even after many turns. Conversation history follows.
    """
    include_temporal = mode in (
        AIMode.BRIEFING_ANALYSIS,
        AIMode.TREND_DETECTION,
        AIMode.CROSS_TOPIC_ANALYSIS,
    )
    context_block = _build_full_context_block(
        context, date_str, include_temporal=include_temporal
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{context_block}\n\nI have questions about this.",
        },
        {
            "role": "assistant",
            "content": "I have the full context. Ask me anything about it.",
        },
    ]

    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": user_question})
    return messages
