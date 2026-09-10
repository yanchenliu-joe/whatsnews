"""User avatar API routes (Phase 37, added 2026-07-06).

Mobile uploads the image directly to Supabase Storage (see migration 0025)
using the signed-in user's own JWT — this endpoint only ever persists the
resulting public URL to profiles.avatar_url. No file upload happens here.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.auth.http_errors import raise_for_auth_repository_error
from app.auth.models import AuthUser
from app.auth.repository import update_avatar_url


class AvatarPatch(BaseModel):
    avatar_url: str = Field(min_length=1, max_length=2048)


def register_avatar_routes(app: FastAPI) -> None:
    @app.patch("/me/avatar")
    def patch_my_avatar(
        body: AvatarPatch,
        user: AuthUser = Depends(get_current_user),
    ):
        avatar_url = body.avatar_url.strip()
        if not avatar_url:
            raise HTTPException(status_code=400, detail="avatar_url must not be empty.")

        try:
            profile = update_avatar_url(user.id, avatar_url)
        except (ValueError, RuntimeError) as error:
            raise_for_auth_repository_error(error, bad_request=True)

        return {
            "id": profile.id,
            "email": profile.email,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
        }
