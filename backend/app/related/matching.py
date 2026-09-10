"""
Related-article scoring (Phase 31, added 2026-07-05).

Pure logic — no DB access, no LLM calls. Ranks a candidate article's title
against a query article's title using two signals:
  1. Shared named entities (reuses briefing/builder.py's extract_entities() —
     the same proper-noun/acronym extractor the narrative briefing layer
     already uses for cross-event thread detection). Primary signal — two
     articles that mention the same entity are usually genuinely related.
  2. Title token Jaccard similarity. Secondary/fallback signal — catches
     related stories that don't share a proper noun (e.g. two articles both
     about "interest rate hikes" with no shared entity).

A score of 0 means "no detected relationship" — callers should exclude these
rather than pad results with unrelated filler.
"""

from __future__ import annotations

import re

from app.briefing.builder import extract_entities

_ENTITY_MATCH_WEIGHT = 10
_SAME_TOPIC_BONUS = 1.0


def _title_tokens(title: str) -> frozenset[str]:
    return frozenset(re.sub(r"[^\w\s]", "", (title or "").lower()).split())


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_query_signature(title: str) -> tuple[frozenset[str], frozenset[str]]:
    """Compute the query article's (entities, title_tokens) once, reuse per candidate."""
    return frozenset(extract_entities([title])), _title_tokens(title)


def score_candidate(
    query_entities: frozenset[str],
    query_tokens: frozenset[str],
    query_topic: str | None,
    candidate_title: str,
    candidate_topic: str | None,
) -> float:
    """Higher is more related. See module docstring for the scoring formula."""
    candidate_entities = extract_entities([candidate_title])
    shared_entities = len(query_entities & candidate_entities)
    jaccard = _jaccard(query_tokens, _title_tokens(candidate_title))

    score = shared_entities * _ENTITY_MATCH_WEIGHT + jaccard
    if query_topic and candidate_topic and query_topic == candidate_topic:
        score += _SAME_TOPIC_BONUS

    return score
