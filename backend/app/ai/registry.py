"""Provider selection."""

from __future__ import annotations

import os

from app.ai.providers.base import AIProvider
from app.ai.providers.openai_provider import OpenAIProvider

_PROVIDERS: dict[str, AIProvider] = {
    "openai": OpenAIProvider(),
}


def get_ai_provider() -> AIProvider:
    name = os.getenv("AI_PROVIDER", "openai").lower().strip()
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unsupported AI_PROVIDER: {name}")
    return provider


def get_provider_name() -> str:
    return get_ai_provider().name
