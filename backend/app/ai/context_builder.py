"""Context Builder — builds structured intelligence context from multiple sources.

Sits between user request and Prompt Builder:
  User → Context Builder → Prompt Builder → Router → LLM

This module is the only place that fetches supporting data from the DB.
It returns a ContextObject that the Prompt Builder formats into messages.
The LLM never sees raw unfiltered data — everything is curated here.

Strict rules enforced here:
  - Max 5 related articles per topic (deduped, recency-filtered)
  - Max 3 cross-topic signals (highest-scoring only)
  - Articles older than 7 days excluded from related pool
  - No vectors, no embeddings, no external ML calls
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.ai.entity_extractor import ExtractedEntity, entity_names, extract_entities
from app.ai.event_detector import Event, detect_events
from app.ai.global_graph import global_graph as _global_graph
from app.ai.influence_engine import InfluenceNode, build_influence_nodes
from app.ai.schemas import AIMode, ArticleContext
from app.briefing_repository import get_active_topics, get_topic_by_name


def _log(event: str, **kwargs) -> None:
    parts = [f"[whatsnews] event=context_builder.{event}"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v!r}")
    print(" ".join(parts), flush=True)


# ─── Domain keyword index ────────────────────────────────────────────────────
#
# Each entry: ([topic_name_fragments], [signal_keywords])
# Fragment matching: topic name contains ANY fragment (case-insensitive)
# Keyword matching: article text (title+summary+wim) contains ANY keyword
# Threshold for a link: ≥ 1 keyword matched

_DOMAIN_SIGNALS: list[tuple[list[str], list[str]]] = [
    # ── Artificial Intelligence ──────────────────────────────────────────────
    # Fragments: topic name must contain one of these to activate this block.
    # Keywords: matched against article text (title + summary + why_it_matters).
    # Phase 23A spec keywords: "ai", "nvidia", "tsmc", "chip"
    (
        ["artificial intelligence", "machine learning", "ai"],
        [
            # Phase 23A explicit requirements
            # "ai " catches "ai model/chip/company" at any position incl. string start
            "ai ", "ai-", " ai,", " ai.", "artificial intelligence",
            "machine learning", "nvidia", "tsmc", "chip", "chips",
            # Extended signal vocabulary
            "llm", "gpt", "openai", "anthropic", "gpu", "neural",
            "deep learning", "model training", "inference", "gemini",
            "large language", "foundation model", "chips act", "semiconductor",
            "transformer", "diffusion model", "autonomous",
        ],
    ),
    # ── Markets / Finance ────────────────────────────────────────────────────
    # Phase 23A spec keywords: "nvidia", "tsmc", "chip", "fed", "interest rate"
    (
        ["market", "finance", "economic", "invest"],
        [
            # Phase 23A explicit requirements
            "nvidia", "tsmc", "chip", "chips", "semiconductor", "shortage",
            "fed ", "federal reserve", "interest rate",
            # Extended signal vocabulary
            "stock", "nasdaq", "s&p", "dow jones", "earnings", "investor",
            "inflation", "gdp", "ipo", "valuation", "equity", "bond yield",
            "hedge fund", "wall street", "market cap", "supply chain",
            "trade deficit", "consumer price",
        ],
    ),
    # ── Geopolitics ──────────────────────────────────────────────────────────
    # Phase 23A spec keywords: "china", "us", "sanctions"
    (
        ["geopolit", "politic", "defense", "global affairs", "foreign"],
        [
            # Phase 23A explicit requirements
            "china", "sanction",
            # Extended (avoiding bare "us" to prevent false positives)
            "russia", "nato", "export control", "tariff", "trade war",
            "taiwan", "ukraine", "diplomacy", "military", "weapon", "nuclear",
            "alliance", "united nations", "security council", "pentagon",
            "g7 ", "g20 ", "white house", "congress",
        ],
    ),
    # ── Climate / Environment ────────────────────────────────────────────────
    (
        ["climate", "environment", "clean energy", "sustainability"],
        [
            "emission", "carbon", "renewable energy", "solar", "wind power",
            "fossil fuel", "esg", "greenhouse", "clean energy", "paris agreement",
            "net zero", "decarboni", "battery storage", "climate change",
        ],
    ),
    # ── Technology / Startups ────────────────────────────────────────────────
    # Phase 23A: "nvidia", "tsmc", "chip" also signal Technology
    (
        ["technology", "tech", "startup", "silicon"],
        [
            # Phase 23A explicit requirements
            "nvidia", "tsmc", "chip", "chips", "semiconductor", "processor",
            # Extended signal vocabulary
            "startup", "venture capital", "silicon valley", "product launch",
            "acquisition", "ipo", "series a", "series b", "unicorn",
            "big tech", "platform", "app store", "software", "hardware",
        ],
    ),
    # ── Health / Biotech ─────────────────────────────────────────────────────
    (
        ["health", "biotech", "pharma", "medical", "life science"],
        [
            "drug approval", "fda ", "clinical trial", "vaccine", "pharmaceutical",
            "hospital", "treatment", "disease", "therapy", "genomic", "cancer",
            "biotech", "clinical", "mortality",
        ],
    ),
    # ── Crypto / Web3 ────────────────────────────────────────────────────────
    (
        ["crypto", "web3", "blockchain", "digital asset"],
        [
            "bitcoin", "ethereum", "crypto", "blockchain", "defi", "nft", "web3",
            "stablecoin", "exchange hack", "token",
        ],
    ),
    # ── Space / Aerospace ────────────────────────────────────────────────────
    (
        ["space", "aerospace", "aviation"],
        [
            "nasa", "spacex", "rocket", "satellite", "launch pad", "orbit",
            "mars mission", "moon ", "esa ", "boeing ",
        ],
    ),
]

MAX_RELATED_ARTICLES = 5
MAX_CROSS_TOPIC_LINKS = 3
RECENCY_WINDOW_DAYS = 7
MIN_KEYWORD_SCORE = 1  # At least 1 keyword match required for a cross-topic link


# ─── Context schemas ──────────────────────────────────────────────────────────

@dataclass
class RelatedArticle:
    title: str
    summary: str
    source: str
    why_it_matters: str
    published_at: str | None


@dataclass
class TopicContext:
    name: str
    recent_articles: list[RelatedArticle] = field(default_factory=list)
    article_count: int = 0


@dataclass
class CrossTopicLink:
    topic: str
    reason: str
    matched_keywords: list[str] = field(default_factory=list)
    overlap_score: float = 0.0
    # Phase 23B: event type that drove this link ("" = keyword-based Phase 23A fallback)
    source_event_type: str = ""


@dataclass
class CrossTopicContext:
    links: list[CrossTopicLink] = field(default_factory=list)


@dataclass
class DailySnapshot:
    topic: str
    top_story_title: str


@dataclass
class TemporalContext:
    today_date: str
    today_snapshots: list[DailySnapshot] = field(default_factory=list)
    prev_day_date: str | None = None
    prev_day_snapshots: list[DailySnapshot] = field(default_factory=list)


@dataclass
class UserContext:
    """
    Reserved for Phase 24+: reading history, bookmarks, preferences.
    Interface defined here so the prompt builder can reference it.
    DO NOT implement storage or retrieval yet.
    """
    pass


@dataclass
class ContextMetadata:
    build_time_ms: int = 0
    related_articles_found: int = 0
    cross_topic_signals: int = 0
    has_temporal_data: bool = False
    db_available: bool = False
    # Phase 23B additions
    events_detected: int = 0
    entities_found: int = 0
    # Phase 23C addition
    influence_nodes_count: int = 0
    # Phase 23D addition
    global_graph_node_count: int = 0
    global_graph_edge_count: int = 0


@dataclass
class ContextObject:
    article_context: ArticleContext
    topic_context: TopicContext
    cross_topic_context: CrossTopicContext
    temporal_context: TemporalContext
    user_context: UserContext | None
    metadata: ContextMetadata
    # Phase 23B additions (default_factory ensures backward compat when omitted)
    event_context: list[Event] = field(default_factory=list)
    entity_context: list[str] = field(default_factory=list)
    # Phase 23C addition
    influence_context: list[InfluenceNode] = field(default_factory=list)
    # Phase 23D addition — snapshot of global graph for prompt injection
    global_graph: dict = field(default_factory=dict)


# ─── Cross-topic detection ────────────────────────────────────────────────────

def _article_search_text(article: ArticleContext) -> str:
    return (
        f"{article.title} {article.summary} {article.why_it_matters}"
    ).lower()


def _score_cross_topic(
    article: ArticleContext,
    target_topic_name: str,
) -> tuple[float, list[str], str]:
    """
    Phase 23A keyword-based cross-topic scorer.
    Retained as fallback when no events are detected.
    Returns (score, matched_keywords, reason). Zero score = no link.
    """
    text = _article_search_text(article)
    topic_lower = target_topic_name.lower()
    matched: list[str] = []

    for topic_fragments, keywords in _DOMAIN_SIGNALS:
        if not any(frag in topic_lower for frag in topic_fragments):
            continue
        for kw in keywords:
            if kw in text:
                matched.append(kw)

    if len(matched) < MIN_KEYWORD_SCORE:
        return 0.0, [], ""

    score = min(1.0, len(matched) / 3.0)
    top_kw = matched[:3]
    reason = (
        f"mentions {', '.join(repr(k) for k in top_kw[:2])}"
        f" — signals {target_topic_name} relevance"
    )
    return score, matched[:5], reason


def _resolve_topic_label(label: str, active_topics: list[dict]) -> str | None:
    """
    Map a generic event topic label (e.g. "Markets", "AI", "Geopolitics")
    to an actual topic name in the DB using the Phase 23A domain signal fragments.
    Returns the first matching active topic name, or None if no match.
    """
    label_lower = label.lower()
    for t in active_topics:
        name_lower = t["name"].lower()
        # Direct substring match in either direction
        if label_lower in name_lower or name_lower in label_lower:
            return t["name"]
    # Fuzzy fallback via _DOMAIN_SIGNALS fragments
    for topic_fragments, _ in _DOMAIN_SIGNALS:
        if any(frag in label_lower for frag in topic_fragments):
            for t in active_topics:
                name_lower = t["name"].lower()
                if any(frag in name_lower for frag in topic_fragments):
                    return t["name"]
    return None


def _event_driven_cross_topics(
    events: list[Event],
    article: ArticleContext,
    active_topics: list[dict],
) -> list[CrossTopicLink]:
    """
    Phase 23B primary path.
    Converts detected events → cross-topic links.
    Each event maps to the topics it affects; entity refinement narrows scope.
    Deduplicates by target topic. Returns up to MAX_CROSS_TOPIC_LINKS links.
    """
    seen_topics: set[str] = set()
    candidates: list[tuple[float, CrossTopicLink]] = []
    article_topic_lower = article.topic.lower()

    for event in events:
        for generic_label in event.topics:
            actual_name = _resolve_topic_label(generic_label, active_topics)
            if not actual_name:
                continue
            if actual_name.lower() == article_topic_lower:
                continue
            if actual_name in seen_topics:
                continue
            seen_topics.add(actual_name)

            reason = (
                f"{event.event_type} detected"
                + (
                    f" — {', '.join(event.entities[:2])}"
                    if event.entities
                    else ""
                )
                + f" → {actual_name} relevance"
            )
            candidates.append((event.confidence, CrossTopicLink(
                topic=actual_name,
                reason=reason,
                matched_keywords=event.entities[:5],
                overlap_score=round(event.confidence, 2),
                source_event_type=event.event_type,
            )))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [lnk for _, lnk in candidates[:MAX_CROSS_TOPIC_LINKS]]


def _keyword_cross_topics(
    article: ArticleContext,
    active_topics: list[dict],
) -> list[CrossTopicLink]:
    """
    Phase 23A keyword fallback path — used when no events are detected.
    source_event_type is left empty to signal keyword-based origin.
    """
    candidates: list[tuple[float, CrossTopicLink]] = []
    for t in active_topics:
        tname: str = t["name"]
        if tname.lower() == article.topic.lower():
            continue
        score, keywords, reason = _score_cross_topic(article, tname)
        if score > 0:
            candidates.append((score, CrossTopicLink(
                topic=tname,
                reason=reason,
                matched_keywords=keywords,
                overlap_score=round(score, 2),
                source_event_type="",   # keyword-based, no event
            )))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [lnk for _, lnk in candidates[:MAX_CROSS_TOPIC_LINKS]]


# ─── DB fetch helpers ─────────────────────────────────────────────────────────

def _fetch_related_articles(cur, topic_id: int, current_url: str) -> list[RelatedArticle]:
    """
    Recent assembled articles for the same topic, excluding current article URL.
    Quality rules enforced:
      - report_id IS NOT NULL (assembled only)
      - why_it_matters must be present
      - within RECENCY_WINDOW_DAYS
      - deduped by title
      - max MAX_RELATED_ARTICLES returned
    """
    cutoff = date.today() - timedelta(days=RECENCY_WINDOW_DAYS)
    cur.execute(
        """
        SELECT a.title,
               COALESCE(a.summary, '')        AS summary,
               COALESCE(a.source, '')         AS source,
               COALESCE(a.why_it_matters, '') AS why_it_matters,
               a.published_at,
               a.url
        FROM articles a
        JOIN daily_reports dr ON dr.id = a.report_id
        WHERE dr.topic_id    = %s
          AND a.report_id    IS NOT NULL
          AND a.why_it_matters IS NOT NULL
          AND TRIM(a.why_it_matters) != ''
          AND (a.url IS NULL OR a.url != %s)
          AND dr.report_date >= %s
        ORDER BY dr.report_date DESC, a.id ASC
        LIMIT %s
        """,
        (topic_id, current_url or "", cutoff, MAX_RELATED_ARTICLES * 2),
    )
    rows = cur.fetchall()

    result: list[RelatedArticle] = []
    seen_titles: set[str] = set()
    for row in rows:
        title = (row["title"] or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        pub = row["published_at"]
        result.append(RelatedArticle(
            title=title,
            summary=(row["summary"] or "").strip(),
            source=(row["source"] or "").strip(),
            why_it_matters=(row["why_it_matters"] or "").strip(),
            published_at=(
                pub.isoformat()
                if hasattr(pub, "isoformat")
                else str(pub) if pub else None
            ),
        ))
        if len(result) >= MAX_RELATED_ARTICLES:
            break

    return result


def _fetch_top_stories(cur, report_date: date) -> list[DailySnapshot]:
    """One top story per topic for the given date."""
    cur.execute(
        """
        SELECT DISTINCT ON (t.sort_order, t.name)
               t.name  AS topic,
               a.title
        FROM daily_reports dr
        JOIN topics  t ON t.id = dr.topic_id
        JOIN articles a ON a.report_id = dr.id
        WHERE dr.report_date = %s
          AND a.why_it_matters IS NOT NULL
          AND TRIM(a.why_it_matters) != ''
        ORDER BY t.sort_order ASC, t.name ASC, a.id ASC
        """,
        (report_date,),
    )
    snapshots: list[DailySnapshot] = []
    for row in cur.fetchall():
        title = (row["title"] or "").strip()
        if title:
            snapshots.append(DailySnapshot(topic=row["topic"], top_story_title=title))
    return snapshots


# ─── Main builder ─────────────────────────────────────────────────────────────

def build_context(
    article: ArticleContext,
    mode: AIMode = AIMode.ARTICLE_INSIGHT,
    date_str: str | None = None,
) -> ContextObject:
    """
    Synchronous context builder — opens its own DB connection.

    Always returns a valid ContextObject. When the DB is unavailable the
    article-only context is returned so the AI still works.

    Call from async contexts via:
        context = await asyncio.to_thread(build_context, article, mode, date_str)
    """
    start = time.monotonic()
    today = date.today()
    today_str = date_str or today.isoformat()

    metadata = ContextMetadata(db_available=False)
    topic_ctx = TopicContext(name=article.topic)
    cross_ctx = CrossTopicContext()
    temporal_ctx = TemporalContext(today_date=today_str)

    # ── Phase 23B+C+D: entity / event / influence / global graph ────────────────
    article_text = (
        f"{article.title} {article.summary} {article.why_it_matters}"
    )
    extracted = extract_entities(article_text)
    events = detect_events(article_text, extracted)
    entity_list = entity_names(extracted)
    # Phase 23C: influence propagation; Phase 23D: feeds global_graph inside
    influence_nodes = build_influence_nodes(
        article_text, extracted, events, article_url=article.url or ""
    )
    # Phase 23D: snapshot AFTER influence nodes are merged into global_graph
    gg_stats = _global_graph.stats()
    global_ctx: dict = {
        "top_nodes": _global_graph.get_top_nodes(20),
        "edges":     _global_graph.get_edges(50),       # last 50 by append order
    }

    metadata.entities_found = len(extracted)
    metadata.events_detected = len(events)
    metadata.influence_nodes_count = len(influence_nodes)
    metadata.global_graph_node_count = gg_stats["total_nodes"]
    metadata.global_graph_edge_count = gg_stats["total_edges"]

    try:
        from app.database import get_connection

        conn = get_connection()
        cur = conn.cursor()
        metadata.db_available = True

        try:
            # 1. Resolve topic_id for the current article's topic
            topic_row = get_topic_by_name(cur, article.topic)
            topic_id: int | None = topic_row["id"] if topic_row else None

            # 2. Topic context: recent related articles in same topic
            if topic_id:
                related = _fetch_related_articles(cur, topic_id, article.url)
                topic_ctx = TopicContext(
                    name=article.topic,
                    recent_articles=related,
                    article_count=len(related),
                )
                metadata.related_articles_found = len(related)

            # 3. Cross-topic detection — Phase 23B primary (event-driven)
            #    Falls back to Phase 23A keyword method when no events found.
            all_active = get_active_topics(cur)
            if events:
                cross_links = _event_driven_cross_topics(events, article, all_active)
            else:
                cross_links = _keyword_cross_topics(article, all_active)
            cross_ctx = CrossTopicContext(links=cross_links)
            metadata.cross_topic_signals = len(cross_links)

            # 4. Temporal context: today's & yesterday's top stories
            today_snaps = _fetch_top_stories(cur, today)
            temporal_ctx = TemporalContext(
                today_date=today_str,
                today_snapshots=today_snaps,
            )
            if today_snaps:
                metadata.has_temporal_data = True

            prev_date = today - timedelta(days=1)
            prev_snaps = _fetch_top_stories(cur, prev_date)
            if prev_snaps:
                temporal_ctx.prev_day_date = prev_date.isoformat()
                temporal_ctx.prev_day_snapshots = prev_snaps

        finally:
            cur.close()
            conn.close()

    except Exception as exc:
        _log("db_error", error=str(exc)[:200])

    build_ms = int((time.monotonic() - start) * 1000)
    metadata.build_time_ms = build_ms

    _log(
        "built",
        mode=mode.value,
        topic=article.topic,
        related_articles=metadata.related_articles_found,
        cross_topic_signals=metadata.cross_topic_signals,
        events_detected=metadata.events_detected,
        entities_found=metadata.entities_found,
        influence_nodes=metadata.influence_nodes_count,
        graph_nodes=metadata.global_graph_node_count,
        graph_edges=metadata.global_graph_edge_count,
        has_temporal=metadata.has_temporal_data,
        db_ok=metadata.db_available,
        build_ms=build_ms,
    )

    return ContextObject(
        article_context=article,
        topic_context=topic_ctx,
        cross_topic_context=cross_ctx,
        temporal_context=temporal_ctx,
        user_context=None,
        metadata=metadata,
        event_context=events,
        entity_context=entity_list,
        influence_context=influence_nodes,
        global_graph=global_ctx,
    )


async def build_context_async(
    article: ArticleContext,
    mode: AIMode = AIMode.ARTICLE_INSIGHT,
    date_str: str | None = None,
) -> ContextObject:
    """Async wrapper — runs synchronous DB operations in a thread pool."""
    return await asyncio.to_thread(build_context, article, mode, date_str)
