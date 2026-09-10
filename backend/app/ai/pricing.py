"""Best-effort OpenAI pricing estimates (USD). Not billing-accurate."""

from __future__ import annotations

# Per 1M tokens unless noted otherwise.
CHAT_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}

# Per 1M characters for TTS models.
TTS_MODEL_PRICING: dict[str, float] = {
    "tts-1": 15.0,
    "tts-1-hd": 30.0,
}

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_TTS_MODEL = "tts-1"


def estimate_chat_cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> float:
    pricing = CHAT_MODEL_PRICING.get(model, CHAT_MODEL_PRICING[DEFAULT_CHAT_MODEL])
    return (input_tokens / 1_000_000) * pricing["input"] + (
        output_tokens / 1_000_000
    ) * pricing["output"]


def estimate_tts_cost_usd(model: str, *, characters: int) -> float:
    rate = TTS_MODEL_PRICING.get(model, TTS_MODEL_PRICING[DEFAULT_TTS_MODEL])
    return (characters / 1_000_000) * rate


def estimate_tokens_from_text(text: str) -> int:
    """Rough token estimate when usage metadata is unavailable."""
    return max(1, len(text or "") // 4)
