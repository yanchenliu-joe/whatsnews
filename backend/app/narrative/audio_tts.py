"""OpenAI text-to-speech synthesis via AI provider abstraction."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.ai.errors import (
    AIErrorCategory,
    build_diagnostic_message,
    category_public_message,
    classify_ai_error,
)
from app.ai.registry import get_ai_provider
from app.narrative.audio_config import get_tts_model, get_tts_provider, get_tts_voice, resolve_tts_voice
from app.narrative.audio_prepare import split_tts_chunks


class TTSConfigurationError(Exception):
    """Raised when TTS cannot run (missing key, unsupported provider)."""

    category = AIErrorCategory.NOT_CONFIGURED

    def __init__(self, diagnostic_message: str) -> None:
        self.diagnostic_message = diagnostic_message
        self.public_message = category_public_message(AIErrorCategory.NOT_CONFIGURED)
        super().__init__(self.public_message)


class TTSGenerationError(Exception):
    """Raised when TTS provider returns an error."""

    def __init__(
        self,
        public_message: str,
        *,
        category: AIErrorCategory,
        diagnostic_message: str | None = None,
    ) -> None:
        self.category = category
        self.public_message = public_message
        self.diagnostic_message = diagnostic_message or public_message
        super().__init__(public_message)


def synthesize_speech(text: str, voice: str | None = None) -> tuple[bytes, str, str]:
    """
    Synthesize speech from prepared script text.

    Returns (audio_bytes, model, voice).
    """
    provider_name = get_tts_provider()
    if provider_name != "openai":
        raise TTSConfigurationError(f"Unsupported VOICE_TTS_PROVIDER: {provider_name}")

    provider = get_ai_provider()
    if not provider.is_configured():
        raise TTSConfigurationError("OPENAI_API_KEY is not configured.")

    if not (text or "").strip():
        raise TTSGenerationError(
            "TTS input text is empty.",
            category=AIErrorCategory.PROVIDER_ERROR,
            diagnostic_message="TTS input text is empty after preparation.",
        )

    model = get_tts_model()
    resolved_voice = resolve_tts_voice(voice)

    try:
        chunks = split_tts_chunks(text)

        def _synth_chunk(indexed_chunk: tuple[int, str]) -> bytes:
            index, chunk = indexed_chunk
            return provider.text_to_speech(
                operation="narrative_tts",
                model=model,
                voice=resolved_voice,
                text=chunk,
                count_as_generation=index == 0,
            )

        # Chunks are independent TTS round-trips (2026-07-06 speed pass) —
        # run them concurrently. ThreadPoolExecutor.map() preserves input
        # order in its result iterator regardless of completion order, so
        # b"".join() below still reassembles the script correctly and
        # count_as_generation still refers to the ORIGINAL first chunk.
        with ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
            audio_parts = list(executor.map(_synth_chunk, enumerate(chunks)))

        return b"".join(audio_parts), model, resolved_voice

    except TTSConfigurationError:
        raise
    except TTSGenerationError:
        raise
    except Exception as exc:
        category = classify_ai_error(exc)
        raise TTSGenerationError(
            category_public_message(category),
            category=category,
            diagnostic_message=build_diagnostic_message(exc),
        ) from exc
