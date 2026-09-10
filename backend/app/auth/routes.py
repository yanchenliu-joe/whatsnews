"""Authenticated user API routes (Phase 18.2)."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from app.auth.deps import get_current_user
from app.auth.http_errors import raise_for_auth_repository_error
from app.auth.models import AuthUser
from app.auth.repository import get_or_create_profile


def register_auth_routes(app: FastAPI) -> None:
    @app.get("/auth/me")
    def get_auth_me(user: AuthUser = Depends(get_current_user)):
        """
        Return the authenticated user's profile.
        Requires Authorization: Bearer <Supabase access_token> when ENABLE_AUTH=true.
        """
        try:
            profile = get_or_create_profile(user)
        except (ValueError, RuntimeError) as error:
            raise_for_auth_repository_error(error)

        return {
            "id": profile.id,
            "email": profile.email,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
        }
