"""User preferences API routes (Phase 18.4)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.auth.http_errors import raise_for_auth_repository_error
from app.auth.models import AuthUser
from app.auth.preferences_repository import get_user_preferences, patch_user_preferences


class PreferencesPatch(BaseModel):
    default_topic: Optional[str] = Field(default=None, max_length=200)
    preferred_voice_profile: Optional[str] = Field(default=None)
    push_notifications_enabled: Optional[bool] = None
    ui_language: Optional[str] = Field(default=None)


def register_preferences_routes(app: FastAPI) -> None:
    @app.get("/me/preferences")
    def get_my_preferences(user: AuthUser = Depends(get_current_user)):
        try:
            return get_user_preferences(user.id)
        except (ValueError, RuntimeError) as error:
            raise_for_auth_repository_error(error)

    @app.patch("/me/preferences")
    def patch_my_preferences(
        body: PreferencesPatch,
        user: AuthUser = Depends(get_current_user),
    ):
        patch: dict[str, Any] = body.model_dump(exclude_unset=True)
        if not patch:
            raise HTTPException(status_code=400, detail="No preference fields provided.")

        try:
            return patch_user_preferences(user.id, patch)
        except (ValueError, RuntimeError) as error:
            raise_for_auth_repository_error(error, bad_request=True)
