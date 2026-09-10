"""Classify AI provider failures for health monitoring."""

from __future__ import annotations

from enum import Enum


class AIErrorCategory(str, Enum):
    NOT_CONFIGURED = "not_configured"
    INVALID_API_KEY = "invalid_api_key"
    INSUFFICIENT_QUOTA = "insufficient_quota"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PROVIDER_ERROR = "provider_error"


def sanitize_error_message(message: str | None, max_len: int = 200) -> str:
    """Strip likely secrets and truncate for admin/server logs."""
    if not message:
        return "Unknown error"
    text = str(message).replace("\n", " ").strip()
    lower = text.lower()
    if "sk-" in lower or "bearer " in lower:
        return "Provider authentication or configuration error."
    for token in ("api_key=", "api key:", "authorization:"):
        if token in lower:
            return "Provider authentication or configuration error."
    return text[:max_len]


def _raw_error_text(exc: BaseException) -> str:
    return str(exc).replace("\n", " ").strip()


def _http_status(exc: BaseException) -> int | None:
    for attr in ("status_code", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
    return None


def classify_ai_error(exc: BaseException) -> AIErrorCategory:
    """Map provider exceptions to a stable health category."""
    name = type(exc).__name__.lower()
    raw = _raw_error_text(exc).lower()
    status = _http_status(exc)

    if "not configured" in raw or name == "ttsconfigurationerror":
        return AIErrorCategory.NOT_CONFIGURED

    if status == 401 or "authentication" in name or "incorrect api key" in raw or "invalid api key" in raw:
        return AIErrorCategory.INVALID_API_KEY

    if status == 429 or "ratelimit" in name or "rate limit" in raw or "too many requests" in raw:
        return AIErrorCategory.RATE_LIMIT

    if status == 402 or (
        "quota" in raw
        or "insufficient" in raw
        or "billing" in raw
        or "exceeded your current quota" in raw
    ):
        return AIErrorCategory.INSUFFICIENT_QUOTA

    if "timeout" in name or "timed out" in raw or status == 408:
        return AIErrorCategory.TIMEOUT

    if (
        "connection" in name
        or "connecterror" in name
        or "network" in raw
        or "connection error" in raw
        or "failed to establish" in raw
    ):
        return AIErrorCategory.NETWORK_ERROR

    return AIErrorCategory.PROVIDER_ERROR


def build_diagnostic_message(exc: BaseException) -> str:
    """Sanitized provider detail for logs and admin diagnostics."""
    status = _http_status(exc)
    body = sanitize_error_message(_raw_error_text(exc))
    if status is not None:
        return f"HTTP {status}: {body}"
    return body


def category_public_message(category: AIErrorCategory) -> str:
    """User-safe message — no provider details."""
    messages = {
        AIErrorCategory.NOT_CONFIGURED: "AI features are not configured on this server.",
        AIErrorCategory.INVALID_API_KEY: "AI service is temporarily unavailable.",
        AIErrorCategory.INSUFFICIENT_QUOTA: "AI service capacity is limited right now.",
        AIErrorCategory.RATE_LIMIT: "AI service is busy. Please try again shortly.",
        AIErrorCategory.TIMEOUT: "AI service timed out. Please try again.",
        AIErrorCategory.NETWORK_ERROR: "AI service is temporarily unavailable.",
        AIErrorCategory.PROVIDER_ERROR: "AI service is temporarily unavailable.",
    }
    return messages.get(category, "AI service is temporarily unavailable.")


def provider_error_payload(exc: BaseException) -> dict:
    """Sanitized provider diagnostics for admin debug endpoints."""
    category = classify_ai_error(exc)
    return {
        "success": False,
        "error_type": category.value,
        "error_code": category.value,
        "http_status": _http_status(exc),
        "message": build_diagnostic_message(exc),
        "public_message": category_public_message(category),
        "provider_exception": type(exc).__name__,
    }
