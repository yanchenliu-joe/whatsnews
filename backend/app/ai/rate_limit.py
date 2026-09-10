"""In-process rate limiter for public AI endpoints (Phase 22 hardening).

Fixed-window counter keyed by an arbitrary string (device id or client IP).
No external dependency (Redis, etc.) — matches the project's existing
in-process cache pattern (see app/feed/service.py). State resets on restart,
which is acceptable here: the goal is to blunt scripted abuse of a real,
OpenAI-backed endpoint, not to provide durable quota accounting.
"""

from __future__ import annotations

import time

_DEFAULT_MAX_REQUESTS = 30
_DEFAULT_WINDOW_SECONDS = 3600

_hits: dict[str, list[float]] = {}


def check_rate_limit(
    key: str,
    *,
    max_requests: int = _DEFAULT_MAX_REQUESTS,
    window_seconds: int = _DEFAULT_WINDOW_SECONDS,
) -> tuple[bool, int]:
    """
    Record a hit for `key` and check whether it exceeds the limit.

    Returns (allowed, retry_after_seconds). retry_after_seconds is 0 when allowed.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    timestamps = [t for t in _hits.get(key, []) if t > cutoff]

    if len(timestamps) >= max_requests:
        retry_after = max(1, int(window_seconds - (now - timestamps[0])))
        _hits[key] = timestamps
        return False, retry_after

    timestamps.append(now)
    _hits[key] = timestamps
    return True, 0


def clear_rate_limits() -> int:
    """Reset all tracked rate-limit state. Used by tests."""
    n = len(_hits)
    _hits.clear()
    return n
