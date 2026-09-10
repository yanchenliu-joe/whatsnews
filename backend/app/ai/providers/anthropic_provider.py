"""Anthropic Claude provider — placeholder (Phase 22+).

Implement by:
1. pip install anthropic
2. Set ANTHROPIC_API_KEY
3. Fill in chat_completion / stream_chat / health using anthropic.Anthropic() client.
4. Register in ai/registry.py: _PROVIDERS["anthropic"] = AnthropicProvider()
5. Set AI_PROVIDER=anthropic (or add task-level override in router.py).
"""

from __future__ import annotations

import os
from typing import AsyncIterator

from app.ai.providers.base import AIProvider, ChatResult, HealthResult


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def is_configured(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def health(self) -> HealthResult:
        return HealthResult(ok=False, latency_ms=0, detail="Not implemented")

    def chat_completion(self, *, operation, model, messages, max_tokens, temperature, response_format=None) -> ChatResult:
        raise NotImplementedError("AnthropicProvider.chat_completion not implemented")

    async def stream_chat(self, *, operation, model, messages, max_tokens, temperature) -> AsyncIterator[str]:
        raise NotImplementedError("AnthropicProvider.stream_chat not implemented")
        yield  # make mypy happy — AsyncIterator requires a yield

    def text_to_speech(self, *, operation, model, voice, text, count_as_generation=True) -> bytes:
        raise NotImplementedError("AnthropicProvider.text_to_speech not implemented")
