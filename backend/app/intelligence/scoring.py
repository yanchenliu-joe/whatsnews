"""
Signal scoring engine (Phase 25).

Computes a 0–100 signal_score for each article using four rule-based components:
  impact_score     (0–30)  — topic relevance + keyword tier + editorial importance
  novelty_score    (0–20)  — recency of publication
  credibility_score (0–20) — source reliability
  urgency_score    (0–30)  — breaking + age

No ML required. Uses editorial_metadata if already computed by the editorial engine.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Keyword tiers ─────────────────────────────────────────────────────────────

_URGENCY_KEYWORDS = frozenset({
    "breaking", "just in", "urgent", "alert", "exclusive", "developing",
    "emergency", "imminent", "live updates", "flash", "crisis",
})

_HIGH_IMPACT_KEYWORDS = frozenset({
    "ban", "sanction", "sanctions", "war", "invasion", "collapse", "crash",
    "breakthrough", "shutdown", "acquisition", "merger", "ipo", "bankruptcy",
    "recall", "pandemic", "epidemic", "disaster", "attack", "assassination",
    "coup", "revolution", "explosion", "earthquake", "default", "tariff",
    "blockade", "embargo", "arrested", "indicted", "impeach",
})

_MEDIUM_IMPACT_KEYWORDS = frozenset({
    "launch", "raises", "funding", "regulation", "lawsuit", "earnings",
    "announces", "deal", "agreement", "treaty", "election", "vote",
    "investigation", "fine", "penalty", "warning", "discovery", "surge",
    "plunges", "record", "historic", "first", "major",
})

_BACKGROUND_KEYWORDS = frozenset({
    "opinion", "analysis", "explainer", "review", "guide", "how to",
    "weekly", "monthly", "roundup", "recap", "preview", "interview",
})


def _tokens(text: str) -> frozenset[str]:
    return frozenset(re.sub(r"[^\w\s]", "", text.lower()).split())


def _age_hours(published_at, now: datetime) -> float | None:
    if not published_at:
        return None
    ts = published_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return max(0.0, (now - ts).total_seconds() / 3600)


def compute_signal_score(
    article: dict,
    source_reliability_score: int,
    now: datetime,
) -> dict:
    """
    Compute signal score for one article.

    Args:
        article: DB row dict (must have title, published_at, editorial_metadata)
        source_reliability_score: 0–100 from news_sources reliability columns
        now: current UTC datetime

    Returns:
        dict with: signal_score, impact_score, novelty_score,
                   credibility_score, urgency_score, signal_tier
    """
    title = article.get("title") or ""
    summary = article.get("summary") or ""
    full_text = (title + " " + summary).lower()
    tok = _tokens(full_text)
    metadata = article.get("editorial_metadata") or {}
    pub_at = article.get("published_at")

    # ── Impact Score (0–30) ───────────────────────────────────────────────────
    # Base from editorial engine's importance_score (0–3 scale → 0–22 base)
    editorial_importance = metadata.get("importance_score") or 0
    try:
        editorial_importance = int(editorial_importance)
    except (TypeError, ValueError):
        editorial_importance = 0

    if editorial_importance >= 3:
        base_impact = 22
    elif editorial_importance >= 2:
        base_impact = 14
    elif editorial_importance >= 1:
        base_impact = 8
    else:
        base_impact = 2

    # Keyword boost
    high_hits = len(tok & _HIGH_IMPACT_KEYWORDS)
    med_hits = len(tok & _MEDIUM_IMPACT_KEYWORDS)
    bg_penalty = 3 if tok & _BACKGROUND_KEYWORDS else 0
    kw_boost = min(8, high_hits * 4 + med_hits * 2) - bg_penalty

    impact_score = max(0, min(30, base_impact + kw_boost))

    # ── Novelty Score (0–20) — recency ────────────────────────────────────────
    age = _age_hours(pub_at, now)
    if age is None:
        novelty_score = 5
    elif age < 6:
        novelty_score = 20
    elif age < 12:
        novelty_score = 17
    elif age < 24:
        novelty_score = 13
    elif age < 48:
        novelty_score = 8
    elif age < 72:
        novelty_score = 4
    else:
        novelty_score = 1

    # ── Credibility Score (0–20) — source reliability ─────────────────────────
    rel = max(0, min(100, source_reliability_score))
    if rel >= 90:
        credibility_score = 20
    elif rel >= 75:
        credibility_score = 16
    elif rel >= 50:
        credibility_score = 11
    elif rel >= 25:
        credibility_score = 6
    else:
        credibility_score = 3

    # ── Urgency Score (0–30) — breaking + age ────────────────────────────────
    has_urgency = bool(tok & _URGENCY_KEYWORDS)
    has_high_impact = bool(tok & _HIGH_IMPACT_KEYWORDS)
    age_urgency = age if age is not None else 48

    if age_urgency < 3 and has_urgency:
        urgency_score = 30
    elif age_urgency < 6 and (has_urgency or has_high_impact):
        urgency_score = 25
    elif age_urgency < 12 and has_high_impact:
        urgency_score = 20
    elif age_urgency < 12:
        urgency_score = 15
    elif age_urgency < 24:
        urgency_score = 10
    elif age_urgency < 48:
        urgency_score = 6
    else:
        urgency_score = 2

    total = impact_score + novelty_score + credibility_score + urgency_score

    return {
        "signal_score": total,
        "impact_score": impact_score,
        "novelty_score": novelty_score,
        "credibility_score": credibility_score,
        "urgency_score": urgency_score,
        "signal_tier": (
            "high"          if total >= 70
            else "informational" if total >= 40
            else "noise"
        ),
    }
