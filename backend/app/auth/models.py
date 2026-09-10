"""Auth models (Phase 18.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuthUser:
    id: str
    email: str | None
    role: str | None = None
    app_metadata: dict[str, Any] | None = None
    user_metadata: dict[str, Any] | None = None


@dataclass
class UserProfile:
    id: str
    email: str | None
    display_name: str | None
    avatar_url: str | None
    created_at: str | None = None
