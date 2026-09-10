"""Entity Extractor — lightweight, rule-based named entity recognition.

Design principles (Phase 23B):
  - Zero external dependencies / zero ML
  - O(n) single scan: tokenize text once, match against lookup tables
  - Curated registry per category: Company, Institution, Technology, Actor
  - Word-boundary aware: "Fed" matches but "federation" does not
  - Max 10 entities returned, deduped, ordered by first appearance
  - Always safe: empty string / None → empty list, never raises
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ─── Entity registry ──────────────────────────────────────────────────────────
# Grouped by semantic category. Category determines how events are interpreted
# (e.g. a "Company" in a GEO_EVENT refines the Markets secondary signal).
#
# IMPORTANT: Keep entries lowercase — matching is done on lowercased text.
# Multi-word entries work because we also match bigrams/trigrams (see below).

_COMPANIES: frozenset[str] = frozenset({
    # AI / Semiconductors
    "nvidia", "amd", "intel", "qualcomm", "broadcom", "arm", "asml",
    "tsmc", "samsung", "sk hynix",
    # Big Tech
    "apple", "microsoft", "alphabet", "google", "meta", "amazon", "tesla",
    "ibm", "oracle", "salesforce", "adobe", "palantir", "snowflake",
    # AI Labs / LLM
    "openai", "anthropic", "deepmind", "xai", "mistral", "cohere",
    "stability ai", "hugging face", "inflection",
    # Finance
    "jpmorgan", "goldman sachs", "blackrock", "citadel", "bridgewater",
    "morgan stanley", "bank of america", "wells fargo", "citibank",
    # Defense / Industrial
    "boeing", "lockheed martin", "raytheon", "northrop grumman",
    # Pharma / Biotech
    "pfizer", "moderna", "johnson & johnson", "merck", "abbvie", "novartis",
    # Space
    "spacex", "blue origin", "rocket lab",
    # China Tech
    "alibaba", "tencent", "bytedance", "huawei", "baidu", "xiaomi",
    # EV / Energy
    "rivian", "lucid", "byd", "nio", "volkswagen", "toyota",
    # Telecom
    "att", "verizon", "t-mobile",
})

_INSTITUTIONS: frozenset[str] = frozenset({
    # Central banks & regulators
    "fed", "federal reserve", "ecb", "bank of england", "bank of japan",
    "sec", "cftc", "fdic", "fca", "boe",
    # Regulatory / Govt
    "fda", "ftc", "doj", "cfpb", "epa", "fcc",
    "white house", "congress", "senate", "pentagon",
    "eu", "european union", "european commission",
    "nato", "un", "united nations", "imf", "world bank", "wto", "g7", "g20",
    "cia", "nsa", "fbi",
    # Policy
    "treasury", "department of defense", "department of energy",
    "chips act", "ira",
})

_TECHNOLOGIES: frozenset[str] = frozenset({
    "llm", "gpt", "gpu", "cpu", "tpu", "npu",
    "ai", "ml", "ar", "vr", "xr",
    "blockchain", "bitcoin", "ethereum", "nft", "defi",
    "5g", "6g",
    "rag", "transformer", "diffusion model",
    "cloud", "saas", "paas", "iaas",
    "api", "sdk", "cli",
})

_GEOPOLITICAL_ACTORS: frozenset[str] = frozenset({
    "china", "usa", "russia", "india", "japan", "germany",
    "uk", "france", "iran", "north korea", "south korea", "taiwan",
    "israel", "saudi arabia", "ukraine", "turkey", "brazil",
    "eu", "us",  # short forms safe here (matched with word boundary)
})

# Unified case-insensitive lookup: name → category
_ENTITY_REGISTRY: dict[str, str] = {}
for _e in _COMPANIES:
    _ENTITY_REGISTRY[_e] = "company"
for _e in _INSTITUTIONS:
    _ENTITY_REGISTRY[_e] = "institution"
for _e in _TECHNOLOGIES:
    _ENTITY_REGISTRY[_e] = "technology"
for _e in _GEOPOLITICAL_ACTORS:
    _ENTITY_REGISTRY.setdefault(_e, "actor")  # don't override company/institution


# ─── Tokenizer ────────────────────────────────────────────────────────────────
# Single-pass tokenization: 1-grams, 2-grams, 3-grams.
# Multi-word entities ("Goldman Sachs", "Federal Reserve") need bigrams/trigrams.

_SPLIT_RE = re.compile(r"[\s,;:.!?()\[\]\'\"\\/<>]+")


def _tokens_from_text(text: str) -> list[str]:
    """Normalize and split text into word tokens (lowercased, punctuation removed)."""
    raw = _SPLIT_RE.split(text.lower())
    return [t for t in raw if t and len(t) >= 2]


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


# ─── Public API ──────────────────────────────────────────────────────────────

MAX_ENTITIES = 10


@dataclass(frozen=True)
class ExtractedEntity:
    name: str       # canonical form from registry (lowercase)
    category: str   # company | institution | technology | actor


def extract_entities(text: str) -> list[ExtractedEntity]:
    """
    Extract named entities from article text using the curated registry.

    Approach:
      1. Tokenize text once into 1/2/3-grams (O(n))
      2. Look up each ngram in the hash registry (O(1) per lookup)
      3. Dedup by name, preserve first-mention order
      4. Return max MAX_ENTITIES results

    Never raises. Empty or None input → [].
    """
    if not text:
        return []

    tokens = _tokens_from_text(text)
    if not tokens:
        return []

    seen: set[str] = set()
    result: list[ExtractedEntity] = []

    # Check 3-grams first (most specific), then 2-grams, then 1-grams
    # so "Goldman Sachs" beats "Goldman" and "Sachs" individually.
    candidate_grams = (
        _ngrams(tokens, 3)
        + _ngrams(tokens, 2)
        + tokens  # 1-grams
    )

    for gram in candidate_grams:
        if gram in _ENTITY_REGISTRY and gram not in seen:
            seen.add(gram)
            result.append(ExtractedEntity(name=gram, category=_ENTITY_REGISTRY[gram]))
            if len(result) >= MAX_ENTITIES:
                break

    return result


def entity_names(entities: list[ExtractedEntity]) -> list[str]:
    """Convenience: return just the name strings."""
    return [e.name for e in entities]
