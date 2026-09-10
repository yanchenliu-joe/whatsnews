"""AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass
class ChatResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class HealthResult:
    ok: bool
    latency_ms: int
    detail: str = ""


class AIProvider(ABC):
    """Minimal provider contract for chat + TTS + streaming."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def health(self) -> HealthResult:
        """Lightweight connectivity check. Must return quickly."""
        ...

    @abstractmethod
    def chat_completion(
        self,
        *,
        operation: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
    ) -> ChatResult: ...

    @abstractmethod
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
        Yields text deltas as they arrive from the model.
        Callers iterate with `async for chunk in provider.stream_chat(...)`.
        """
        ...

    @abstractmethod
    def text_to_speech(
        self,
        *,
        operation: str,
        model: str,
        voice: str,
        text: str,
        count_as_generation: bool = True,
    ) -> bytes: ...
