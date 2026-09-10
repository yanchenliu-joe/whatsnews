"""In-process AI health monitoring."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from app.ai.errors import AIErrorCategory, category_public_message, sanitize_error_message


HealthStatus = str  # healthy | warning | degraded | unavailable


@dataclass
class AIFailureRecord:
    operation: str
    provider: str
    category: AIErrorCategory
    diagnostic_message: str
    public_message: str
    at: str


@dataclass
class _HealthState:
    failures: deque[AIFailureRecord] = field(default_factory=lambda: deque(maxlen=50))
    last_success_at: str | None = None
    last_success_operation: str | None = None
    last_error: AIFailureRecord | None = None
    simulated_status: HealthStatus | None = None


_state = _HealthState()
_lock = Lock()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def record_ai_success(*, operation: str, provider: str) -> None:
    with _lock:
        if _state.simulated_status is None:
            _state.last_success_at = _now_iso()
            _state.last_success_operation = operation


def record_ai_failure(
    *,
    operation: str,
    provider: str,
    category: AIErrorCategory,
    diagnostic_message: str | None = None,
    public_message: str | None = None,
) -> None:
    record = AIFailureRecord(
        operation=operation,
        provider=provider,
        category=category,
        diagnostic_message=sanitize_error_message(diagnostic_message),
        public_message=public_message or category_public_message(category),
        at=_now_iso(),
    )
    with _lock:
        _state.failures.appendleft(record)
        _state.last_error = record
        if _state.simulated_status is not None:
            return


def simulate_health_status(status: HealthStatus, *, category: AIErrorCategory | None = None) -> None:
    """Admin-only test hook for health UI verification."""
    with _lock:
        _state.simulated_status = status
        if category and status != "healthy":
            record_ai_failure(
                operation="simulate",
                provider=get_provider_name_for_simulation(),
                category=category,
                diagnostic_message=f"Simulated {category.value} for testing",
            )


def clear_health_simulation() -> None:
    with _lock:
        _state.simulated_status = None


def get_provider_name_for_simulation() -> str:
    import os

    return os.getenv("AI_PROVIDER", "openai")


def _recent_failures(within: timedelta) -> list[AIFailureRecord]:
    cutoff = datetime.now(tz=timezone.utc) - within
    out: list[AIFailureRecord] = []
    for item in _state.failures:
        try:
            at = datetime.fromisoformat(item.at)
        except ValueError:
            continue
        if at >= cutoff:
            out.append(item)
    return out


def compute_health_status(*, api_configured: bool) -> HealthStatus:
    with _lock:
        if _state.simulated_status:
            return _state.simulated_status

    if not api_configured:
        return "warning"

    recent_15 = _recent_failures(timedelta(minutes=15))
    recent_60 = _recent_failures(timedelta(hours=1))

    critical = {
        AIErrorCategory.INVALID_API_KEY,
        AIErrorCategory.INSUFFICIENT_QUOTA,
    }
    if any(f.category in critical for f in recent_15):
        return "unavailable"

    soft = {
        AIErrorCategory.RATE_LIMIT,
        AIErrorCategory.TIMEOUT,
        AIErrorCategory.NETWORK_ERROR,
        AIErrorCategory.PROVIDER_ERROR,
    }
    if len(recent_15) >= 3 or any(f.category in soft for f in recent_15):
        return "degraded"

    if recent_60:
        return "warning"

    return "healthy"


def get_health_snapshot(*, api_configured: bool) -> dict[str, Any]:
    status = compute_health_status(api_configured=api_configured)
    with _lock:
        last_success_at = _state.last_success_at
        last_success_operation = _state.last_success_operation
        last_error = _state.last_error
        recent = list(_state.failures)[:10]

    return {
        "status": status,
        "api_configured": api_configured,
        "last_success_at": last_success_at,
        "last_success_operation": last_success_operation,
        "last_error": (
            {
                "operation": last_error.operation,
                "provider": last_error.provider,
                "type": last_error.category.value,
                "code": last_error.category.value,
                "category": last_error.category.value,
                "message": last_error.diagnostic_message,
                "public_message": last_error.public_message,
                "at": last_error.at,
            }
            if last_error
            else None
        ),
        "recent_failures": [
            {
                "operation": f.operation,
                "provider": f.provider,
                "type": f.category.value,
                "code": f.category.value,
                "category": f.category.value,
                "message": f.diagnostic_message,
                "public_message": f.public_message,
                "at": f.at,
            }
            for f in recent
        ],
    }
