"""OpenAI implementation of AIProvider."""

from __future__ import annotations

import os
import time
from typing import AsyncIterator

from app.ai.errors import AIErrorCategory, build_diagnostic_message, classify_ai_error
from app.ai.health import record_ai_failure, record_ai_success
from app.ai.openai_client import create_async_openai_client, create_openai_client
from app.ai.pricing import DEFAULT_CHAT_MODEL, estimate_tokens_from_text
from app.ai.providers.base import AIProvider, ChatResult, HealthResult
from app.ai.usage import record_chat_usage, record_tts_usage


class OpenAIProvider(AIProvider):
    name = "openai"

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _client(self):
        return create_openai_client()

    def health(self) -> HealthResult:
        if not self.is_configured():
            return HealthResult(ok=False, latency_ms=0, detail="OPENAI_API_KEY not set")
        start = time.monotonic()
        try:
            self._client().models.list()
            latency_ms = int((time.monotonic() - start) * 1000)
            return HealthResult(ok=True, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return HealthResult(ok=False, latency_ms=latency_ms, detail=str(exc)[:200])

    def chat_completion(
        self,
        *,
        operation: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
    ) -> ChatResult:
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        try:
            kwargs = {
                "model": model or DEFAULT_CHAT_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = self._client().chat.completions.create(**kwargs)
            text = (response.choices[0].message.content or "").strip()
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            output_tokens = getattr(usage, "completion_tokens", None) if usage else None
            if input_tokens is None:
                prompt_text = " ".join(m.get("content", "") for m in messages)
                input_tokens = estimate_tokens_from_text(prompt_text)
            if output_tokens is None:
                output_tokens = estimate_tokens_from_text(text)

            record_chat_usage(
                operation=operation,
                model=model or DEFAULT_CHAT_MODEL,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )
            record_ai_success(operation=operation, provider=self.name)
            return ChatResult(
                text=text,
                model=model or DEFAULT_CHAT_MODEL,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )
        except Exception as exc:
            category = classify_ai_error(exc)
            record_ai_failure(
                operation=operation,
                provider=self.name,
                category=category,
                diagnostic_message=build_diagnostic_message(exc),
            )
            raise

    async def stream_chat(
        self,
        *,
        operation: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """
        Yields text delta strings from the OpenAI streaming API.
        Callers must iterate with `async for chunk in provider.stream_chat(...)`.
        """
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        client = create_async_openai_client()
        total_output_chars = 0
        try:
            stream = await client.chat.completions.create(
                model=model or DEFAULT_CHAT_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    total_output_chars += len(delta)
                    yield delta

            # Best-effort usage recording after stream completes
            prompt_text = " ".join(m.get("content", "") for m in messages)
            input_tokens = estimate_tokens_from_text(prompt_text)
            output_tokens = max(1, total_output_chars // 4)
            record_chat_usage(
                operation=operation,
                model=model or DEFAULT_CHAT_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            record_ai_success(operation=operation, provider=self.name)
        except Exception as exc:
            category = classify_ai_error(exc)
            record_ai_failure(
                operation=operation,
                provider=self.name,
                category=category,
                diagnostic_message=build_diagnostic_message(exc),
            )
            raise

    def text_to_speech(
        self,
        *,
        operation: str,
        model: str,
        voice: str,
        text: str,
        count_as_generation: bool = True,
    ) -> bytes:
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        try:
            response = self._client().audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="mp3",
            )
            data = response.content
            record_tts_usage(
                model=model,
                characters=len(text),
                chunks=1,
                count_as_generation=count_as_generation,
            )
            record_ai_success(operation=operation, provider=self.name)
            return data
        except Exception as exc:
            category = classify_ai_error(exc)
            record_ai_failure(
                operation=operation,
                provider=self.name,
                category=category,
                diagnostic_message=build_diagnostic_message(exc),
            )
            raise
