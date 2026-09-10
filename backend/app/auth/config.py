"""Auth configuration (Phase 18.1A — env safety only; no routes wired yet)."""

import os


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def auth_enabled() -> bool:
    """True only when ENABLE_AUTH=true. Default false — Phase 17.5 behavior."""
    return _env_bool("ENABLE_AUTH", "false")


def supabase_url() -> str | None:
    """Optional; not required when auth is disabled."""
    return os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL") or None


def supabase_jwt_secret() -> str | None:
    """Optional; not required when auth is disabled."""
    return os.getenv("SUPABASE_JWT_SECRET") or None
