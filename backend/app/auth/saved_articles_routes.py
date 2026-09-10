"""Saved articles API routes (Phase 18.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.auth.http_errors import raise_for_auth_repository_error
from app.auth.models import AuthUser
from app.auth.saved_articles_repository import (
    delete_saved_article,
    list_saved_articles,
    upsert_saved_article,
)


class SavedArticleCreate(BaseModel):
    article_url: str = Field(min_length=1)
    article_id: Optional[int] = None
    article_title: Optional[str] = None
    topic: Optional[str] = None
    source: Optional[str] = None
    summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    saved_at: Optional[datetime] = None


def register_saved_articles_routes(app: FastAPI) -> None:
    @app.get("/me/saved-articles")
    def get_my_saved_articles(user: AuthUser = Depends(get_current_user)):
        try:
            items = list_saved_articles(user.id)
        except (ValueError, RuntimeError) as error:
            raise_for_auth_repository_error(error)

        return {"items": items, "count": len(items)}

    @app.post("/me/saved-articles")
    def save_my_saved_article(
        body: SavedArticleCreate,
        user: AuthUser = Depends(get_current_user),
    ):
        try:
            item = upsert_saved_article(user.id, body.model_dump(exclude_none=True))
        except (ValueError, RuntimeError) as error:
            raise_for_auth_repository_error(error, bad_request=True)

        return item

    @app.delete("/me/saved-articles/{identifier}")
    def delete_my_saved_article(
        identifier: str,
        user: AuthUser = Depends(get_current_user),
    ):
        try:
            deleted = delete_saved_article(user.id, identifier)
        except RuntimeError as error:
            raise_for_auth_repository_error(error)

        return {"deleted": deleted, "identifier": identifier}
