"""In-memory cache for AI-refined why_it_matters text."""

import hashlib

_CACHE_VERSION = "wim_v2"
_refinement_cache: dict[str, str] = {}


def refinement_cache_key(title: str, summary: str, topic: str) -> str:
    content = f"{_CACHE_VERSION}|{title}|{summary}|{topic}"
    return hashlib.sha256(content.encode()).hexdigest()


def get_cached_refinement(title: str, summary: str, topic: str) -> str | None:
    return _refinement_cache.get(refinement_cache_key(title, summary, topic))


def set_cached_refinement(title: str, summary: str, topic: str, text: str) -> None:
    _refinement_cache[refinement_cache_key(title, summary, topic)] = text
