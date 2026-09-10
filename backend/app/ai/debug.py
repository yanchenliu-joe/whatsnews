"""Temporary admin debug helpers for OpenAI connectivity."""

from __future__ import annotations

import os
import time
from typing import Any

from app.ai.errors import AIErrorCategory, provider_error_payload
from app.ai.openai_client import create_openai_client, get_openai_max_retries, get_openai_timeout_seconds
from app.narrative.audio_tts import (
    TTSConfigurationError,
    TTSGenerationError,
    synthesize_speech,
)


DEBUG_OPENAI_MODEL = os.getenv("OPENAI_DEBUG_MODEL", "gpt-4.1-mini")
DEBUG_PROMPT = "Reply with exactly: OK"


def _extract_responses_text(response: Any) -> str:
    if getattr(response, "output_text", None):
        return str(response.output_text).strip()
    output = getattr(response, "output", None) or []
    parts: list[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()


def debug_openai_responses() -> dict[str, Any]:
    """Single minimal Responses API call."""
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "success": False,
            "error_type": AIErrorCategory.NOT_CONFIGURED.value,
            "error_code": AIErrorCategory.NOT_CONFIGURED.value,
            "http_status": None,
            "message": "OPENAI_API_KEY is not configured.",
        }

    start = time.perf_counter()
    try:
        client = create_openai_client()
        response = client.responses.create(
            model=DEBUG_OPENAI_MODEL,
            input=DEBUG_PROMPT,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        output = _extract_responses_text(response)
        return {
            "success": True,
            "latency_ms": latency_ms,
            "model": DEBUG_OPENAI_MODEL,
            "output": output,
            "timeout_seconds": get_openai_timeout_seconds(),
            "max_retries": get_openai_max_retries(),
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        payload = provider_error_payload(exc)
        payload["latency_ms"] = latency_ms
        payload["model"] = DEBUG_OPENAI_MODEL
        return payload


def debug_tts_synthesis(text: str) -> dict[str, Any]:
    """Run narrative TTS code path only (no DB/storage)."""
    start = time.perf_counter()
    try:
        audio_bytes, model, voice = synthesize_speech(text)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "success": True,
            "latency_ms": latency_ms,
            "model": model,
            "voice": voice,
            "audio_bytes": len(audio_bytes),
            "text_length": len(text),
            "timeout_seconds": get_openai_timeout_seconds(),
            "max_retries": get_openai_max_retries(),
        }
    except TTSConfigurationError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "success": False,
            "error_type": exc.category.value,
            "error_code": exc.category.value,
            "http_status": None,
            "message": exc.diagnostic_message,
            "public_message": exc.public_message,
            "latency_ms": latency_ms,
        }
    except TTSGenerationError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "success": False,
            "error_type": exc.category.value,
            "error_code": exc.category.value,
            "http_status": None,
            "message": exc.diagnostic_message,
            "public_message": exc.public_message,
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        payload = provider_error_payload(exc)
        payload["latency_ms"] = latency_ms
        return payload
