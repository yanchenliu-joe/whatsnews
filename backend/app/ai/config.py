"""Centralized AI Intelligence Platform configuration (Phase 22).

All model names are resolved from env vars so no hardcoded values appear in
business logic. Operators can swap model tiers without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AIChatConfig:
    # Routing tiers
    default_model: str
    cheap_model: str
    reasoning_model: str
    translation_model: str

    # Behaviour
    streaming_enabled: bool
    max_context_tokens: int
    max_response_tokens: int
    temperature: float

    # Provider
    default_provider: str


def get_ai_chat_config() -> AIChatConfig:
    return AIChatConfig(
        default_model=os.getenv("AI_DEFAULT_MODEL", "gpt-4o-mini"),
        cheap_model=os.getenv("AI_CHEAP_MODEL", "gpt-4o-mini"),
        reasoning_model=os.getenv("AI_REASONING_MODEL", "gpt-4o"),
        translation_model=os.getenv("AI_TRANSLATION_MODEL", "gpt-4o-mini"),
        streaming_enabled=os.getenv("AI_STREAMING_ENABLED", "true").lower() != "false",
        max_context_tokens=int(os.getenv("AI_MAX_CONTEXT_TOKENS", "8000")),
        max_response_tokens=int(os.getenv("AI_MAX_RESPONSE_TOKENS", "1200")),
        temperature=float(os.getenv("AI_TEMPERATURE", "0.7")),
        default_provider=os.getenv("AI_PROVIDER", "openai").lower(),
    )
