"""
Cognitive scoring engine (Phase 27).

Computes:
  impact_level: critical / high / medium / low (from signal_score)
  risk_level:   high / medium / low            (from keyword analysis)
  confidence:   0–100                          (from source count + clustering)
"""

from __future__ import annotations

import re

from app.cognitive.templates import HIGH_RISK_KEYWORDS, MEDIUM_RISK_KEYWORDS


def compute_impact_level(signal_score: int) -> str:
    if signal_score >= 80:
        return "critical"
    elif signal_score >= 60:
        return "high"
    elif signal_score >= 40:
        return "medium"
    return "low"


def compute_risk_level(narrative_block: dict) -> str:
    """
    Classify risk using keyword presence across headline + what_happened + so_what.
    High-risk keywords override medium-risk keywords.
    """
    texts = [
        narrative_block.get("headline", ""),
        narrative_block.get("what_happened", ""),
        narrative_block.get("why_it_matters", ""),
    ]
    combined = re.sub(r"[^\w\s]", "", " ".join(texts).lower())
    tokens = set(combined.split())

    if tokens & HIGH_RISK_KEYWORDS:
        return "high"
    if tokens & MEDIUM_RISK_KEYWORDS:
        return "medium"
    return "low"


def compute_confidence(narrative_block: dict) -> int:
    """
    Estimate confidence (0–100) that this event is correctly classified.

    Factors:
      - sources_count:              +15 per additional source (base 1), max +45
      - supporting_article_count:   +8 if ≥3 articles confirmed the story
      - signal_score:               ±10 quality adjustment
    """
    sources = narrative_block.get("sources_count", 1)
    articles = narrative_block.get("supporting_article_count", 1)
    signal = narrative_block.get("signal_score", 50)

    base = 50

    # Multi-source confirmation
    source_pts = min(45, (sources - 1) * 15)

    # Clustering strength
    if articles >= 3:
        cluster_pts = 8
    elif articles >= 2:
        cluster_pts = 4
    else:
        cluster_pts = 0

    # Signal quality proxy
    if signal >= 85:
        quality_pts = 10
    elif signal >= 70:
        quality_pts = 5
    elif signal < 50:
        quality_pts = -10
    else:
        quality_pts = 0

    return max(15, min(100, base + source_pts + cluster_pts + quality_pts))
