"""Shared OpenAI client configuration (timeout, retries)."""

from __future__ import annotations

import os

import httpx


def get_openai_timeout_seconds() -> float:
    return float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))


def get_openai_connect_timeout_seconds() -> float:
    return float(os.getenv("OPENAI_CONNECT_TIMEOUT_SECONDS", "10"))


def get_openai_max_retries() -> int:
    """Default 0 during dev — fail fast instead of long retry loops."""
    return int(os.getenv("OPENAI_MAX_RETRIES", "0"))


def _make_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        get_openai_timeout_seconds(),
        connect=get_openai_connect_timeout_seconds(),
    )


def _api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return api_key


def create_openai_client():
    from openai import OpenAI

    return OpenAI(
        api_key=_api_key(),
        timeout=_make_timeout(),
        max_retries=get_openai_max_retries(),
    )


def create_async_openai_client():
    """Async client for streaming endpoints (Phase 22 AI chat)."""
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=_api_key(),
        timeout=_make_timeout(),
        max_retries=get_openai_max_retries(),
    )
