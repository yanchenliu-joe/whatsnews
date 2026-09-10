"""In-process AI usage counters and cost estimates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from threading import Lock

from app.ai.pricing import estimate_chat_cost_usd, estimate_tts_cost_usd


@dataclass
class _DailyUsage:
    wim_refine_count: int = 0
    narrative_refine_count: int = 0
    tts_generation_count: int = 0
    chat_calls: int = 0
    tts_calls: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class _UsageState:
    day: date = field(default_factory=lambda: datetime.now(tz=timezone.utc).date())
    today: _DailyUsage = field(default_factory=_DailyUsage)
    month_key: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).strftime("%Y-%m")
    )
    month_to_date_cost_usd: float = 0.0


_state = _UsageState()
_lock = Lock()


def _rollover_if_needed() -> None:
    now = datetime.now(tz=timezone.utc)
    today = now.date()
    month_key = now.strftime("%Y-%m")
    if _state.day != today:
        _state.day = today
        _state.today = _DailyUsage()
    if _state.month_key != month_key:
        _state.month_key = month_key
        _state.month_to_date_cost_usd = 0.0


def record_chat_usage(
    *,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    cost = estimate_chat_cost_usd(model, input_tokens=input_tokens, output_tokens=output_tokens)
    with _lock:
        _rollover_if_needed()
        _state.today.chat_calls += 1
        _state.today.estimated_cost_usd += cost
        _state.month_to_date_cost_usd += cost
        if operation in ("wim_refine", "wim_batch"):
            _state.today.wim_refine_count += 1
        elif operation == "narrative_refine":
            _state.today.narrative_refine_count += 1


def record_tts_usage(
    *,
    model: str,
    characters: int,
    chunks: int = 1,
    count_as_generation: bool = True,
) -> None:
    cost = estimate_tts_cost_usd(model, characters=characters)
    with _lock:
        _rollover_if_needed()
        _state.today.tts_calls += chunks
        if count_as_generation:
            _state.today.tts_generation_count += 1
        _state.today.estimated_cost_usd += cost
        _state.month_to_date_cost_usd += cost


def get_session_usage_snapshot() -> dict:
    with _lock:
        _rollover_if_needed()
        return {
            "wim_refine_count": _state.today.wim_refine_count,
            "narrative_refine_count": _state.today.narrative_refine_count,
            "tts_generation_count": _state.today.tts_generation_count,
            "chat_calls": _state.today.chat_calls,
            "tts_calls": _state.today.tts_calls,
            "estimated_cost_usd": round(_state.today.estimated_cost_usd, 6),
            "month_to_date_estimated_cost_usd": round(_state.month_to_date_cost_usd, 6),
        }
