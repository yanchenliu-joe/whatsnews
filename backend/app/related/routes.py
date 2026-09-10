"""Related articles routes (Phase 31)."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from app.related.service import get_related_articles
from app.log_utils import _log


def register_related_routes(app: FastAPI) -> None:

    @app.get("/articles/related")
    def articles_related(
        title: str = Query(..., description="Title of the article to find related stories for"),
        topic: Optional[str] = Query(None, description="Topic of the source article — used as a small scoring nudge, not a filter"),
        exclude_url: Optional[str] = Query(None, description="URL to exclude from results (the source article itself)"),
        limit: int = Query(5, ge=1, le=20),
    ):
        """
        Entity/keyword-overlap related articles for a given article title.

        No embeddings — ranks candidates from the last 7 days (all active
        topics) by shared named entities (primary signal) plus title token
        Jaccard similarity (secondary signal). Returns {"items": []} when
        nothing scores above the relevance floor, rather than padding with
        unrelated filler.
        """
        try:
            items = get_related_articles(title, topic, exclude_url, limit)
        except Exception as exc:
            _log("related_articles_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Related articles error. Please try again.")
        return {"items": items}
