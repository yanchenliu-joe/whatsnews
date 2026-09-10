"""
Feed normalizer (Phase 28).

Maps each intelligence layer's native output to the unified item schema.
One function per mode; all return list[dict] with identical keys.

Unified item schema:
  headline      str          — one-line event statement
  summary       str          — factual what-happened
  so_what       str | None   — cognitive: "why should I care?"
  impact_level  str | None   — cognitive: critical/high/medium/low
  risk_level    str | None   — cognitive: high/medium/low
  confidence    int | None   — cognitive: 0–100
  signal_score  int | None   — phases 25–27
  sources       list[str]    — contributing source names
  sources_count int          — number of distinct sources
  published_at  str | None   — ISO timestamp of lead article
"""

from __future__ import annotations


def _item(
    headline: str = "",
    summary: str = "",
    body_text: str | None = None,
    so_what: str | None = None,
    impact_level: str | None = None,
    risk_level: str | None = None,
    confidence: int | None = None,
    signal_score: int | None = None,
    sources: list | None = None,
    sources_count: int = 0,
    published_at: str | None = None,
    url: str | None = None,
    image_url: str | None = None,
    topic: str | None = None,
) -> dict:
    return {
        "headline":     headline,
        "summary":      summary,
        "body_text":    body_text,
        "so_what":      so_what,
        "impact_level": impact_level,
        "risk_level":   risk_level,
        "confidence":   confidence,
        "signal_score": signal_score,
        "sources":      sources or [],
        "sources_count": sources_count,
        "published_at": published_at,
        "url":          url,
        "image_url":    image_url,
        "topic":        topic,
    }


def _lead_published_at(event_or_block: dict) -> str | None:
    articles = event_or_block.get("top_articles") or []
    if articles:
        return articles[0].get("published_at")
    return None


# ── Per-mode normalizers ──────────────────────────────────────────────────────

def normalize_raw(data: dict) -> list[dict]:
    """
    raw mode: each article becomes one item.
    No signal scoring, no cognitive enrichment.
    """
    articles = data.get("articles", [])
    items = []
    for a in articles:
        pub = a.get("published_at")
        source = a.get("source") or ""
        wim = a.get("why_it_matters") or None
        body = a.get("body_text") or None
        items.append(_item(
            headline=a.get("title") or "",
            summary=a.get("summary") or "",
            body_text=body,
            so_what=wim,
            sources=[source] if source else [],
            sources_count=1,
            published_at=pub.isoformat() if hasattr(pub, "isoformat") else pub,
            url=a.get("url") or None,
            image_url=a.get("image_url") or None,
            topic=a.get("topic_name") or None,
        ))
    return items


def normalize_signal(data: dict) -> list[dict]:
    """
    signal mode: events from Phase 25.
    Signal score + dedup visible; no narrative structure.
    """
    events = data.get("events", [])
    return [
        _item(
            headline=e.get("event_title", ""),
            summary=e.get("summary", ""),
            signal_score=e.get("signal_score"),
            sources=e.get("sources", []),
            sources_count=e.get("sources_count", 0),
            published_at=_lead_published_at(e),
        )
        for e in events
    ]


def normalize_briefing(data: dict) -> list[dict]:
    """
    briefing mode: Phase 26 narrative blocks.
    Structured narrative without cognitive classification.
    """
    primary  = data.get("briefing", [])
    emerging = data.get("emerging_signals", [])
    items = []
    for nb in primary + emerging:
        lead = (nb.get("top_articles") or [{}])[0]
        items.append(_item(
            headline=nb.get("headline", ""),
            summary=nb.get("what_happened", ""),
            body_text=lead.get("body_text") or None,
            so_what=nb.get("why_it_matters") or nb.get("summary"),
            signal_score=nb.get("signal_score"),
            sources=nb.get("sources", []),
            sources_count=nb.get("sources_count", 0),
            published_at=_lead_published_at(nb),
            url=lead.get("url") or None,
            image_url=lead.get("image_url") or None,
        ))
    return items


def normalize_cognitive(data: dict) -> list[dict]:
    """
    cognitive mode: Phase 27 cognitive blocks — full schema.
    All cognitive fields populated.
    """
    primary  = data.get("briefing", [])
    emerging = data.get("emerging_signals", [])
    items = []
    for cb in primary + emerging:
        lead = (cb.get("top_articles") or [{}])[0]
        items.append(_item(
            headline=cb.get("headline", ""),
            summary=cb.get("what_happened", ""),
            body_text=lead.get("body_text") or None,
            so_what=cb.get("so_what"),
            impact_level=cb.get("impact_level"),
            risk_level=cb.get("risk_level"),
            confidence=cb.get("confidence"),
            signal_score=cb.get("signal_score"),
            sources=cb.get("sources", []),
            sources_count=cb.get("sources_count", 0),
            published_at=_lead_published_at(cb),
            url=lead.get("url") or None,
            image_url=lead.get("image_url") or None,
        ))
    return items
