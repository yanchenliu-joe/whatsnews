"""Google Gemini provider — placeholder (Phase 22+).

Implement by:
1. pip install google-generativeai
2. Set GOOGLE_API_KEY
3. Fill in using google.generativeai.GenerativeModel().
4. Register in ai/registry.py: _PROVIDERS["gemini"] = GeminiProvider()
"""

from __future__ import annotations

import os
from typing import AsyncIterator

from app.ai.providers.base import AIProvider, ChatResult, HealthResult


class GeminiProvider(AIProvider):
    name = "gemini"

    def is_configured(self) -> bool:
        return bool(os.getenv("GOOGLE_API_KEY"))

    def health(self) -> HealthResult:
        return HealthResult(ok=False, latency_ms=0, detail="Not implemented")

    def chat_completion(self, *, operation, model, messages, max_tokens, temperature, response_format=None) -> ChatResult:
        raise NotImplementedError("GeminiProvider.chat_completion not implemented")

    async def stream_chat(self, *, operation, model, messages, max_tokens, temperature) -> AsyncIterator[str]:
        raise NotImplementedError("GeminiProvider.stream_chat not implemented")
        yield

    def text_to_speech(self, *, operation, model, voice, text, count_as_generation=True) -> bytes:
        raise NotImplementedError("GeminiProvider.text_to_speech not implemented")
