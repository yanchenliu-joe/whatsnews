"""Alibaba Qwen provider — placeholder (Phase 22+).

Implement by:
1. pip install openai  (Qwen is OpenAI-compatible via DashScope)
2. Set QWEN_API_KEY
3. Use openai.OpenAI(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", api_key=...).
4. Register in ai/registry.py: _PROVIDERS["qwen"] = QwenProvider()
"""

from __future__ import annotations

import os
from typing import AsyncIterator

from app.ai.providers.base import AIProvider, ChatResult, HealthResult


class QwenProvider(AIProvider):
    name = "qwen"

    def is_configured(self) -> bool:
        return bool(os.getenv("QWEN_API_KEY"))

    def health(self) -> HealthResult:
        return HealthResult(ok=False, latency_ms=0, detail="Not implemented")

    def chat_completion(self, *, operation, model, messages, max_tokens, temperature, response_format=None) -> ChatResult:
        raise NotImplementedError("QwenProvider.chat_completion not implemented")

    async def stream_chat(self, *, operation, model, messages, max_tokens, temperature) -> AsyncIterator[str]:
        raise NotImplementedError("QwenProvider.stream_chat not implemented")
        yield

    def text_to_speech(self, *, operation, model, voice, text, count_as_generation=True) -> bytes:
        raise NotImplementedError("QwenProvider.text_to_speech not implemented")
