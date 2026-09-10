"""
Historical briefing API routes.

Endpoints (all read-only, publishable briefings only):

  GET /history              — recent briefing summaries (optional ?topic, ?limit)
  GET /history/dates        — date index for calendar/chips (?topic, ?limit)
  GET /history/date/{date}  — all topics for one date (404 if none publishable)
  GET /history/topic/{name} — topic history by date (404 if topic missing or empty)
  GET /history/search       — ILIKE keyword search (?q min 3 chars, ?topic, ?limit, ?offset)

Empty list vs 404:
  - /history/dates returns empty dates[] when no archive (200)
  - /history/search returns total=0 when no matches (200)
  - /history/date/{date} returns 404 when no publishable briefings for that date
  - /history/topic/{name} returns 404 when topic not found or no publishable history
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from app.briefing_repository import (
    get_briefings_for_date,
    get_topic_by_name,
    get_topic_history,
    list_briefing_dates,
    list_recent_history,
    normalize_search_query,
    parse_report_date,
    search_briefings,
    validate_report_date,
)
from app.database import get_connection
from app.log_utils import _log


def _open_db():
    try:
        return get_connection()
    except ValueError as e:
        _log("internal_error_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Internal server error. Please try again.")


@contextmanager
def _db_cursor():
    conn = _open_db()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
        conn.close()


def _parse_path_date(report_date: str) -> date:
    try:
        parsed = parse_report_date(report_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date. Use YYYY-MM-DD.",
        )
    try:
        validate_report_date(parsed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return parsed


def register_history_routes(app: FastAPI) -> None:
    """Attach /history* endpoints to the FastAPI app."""

    @app.get("/history")
    def get_history(
        limit: int = Query(default=30, ge=1, le=365),
        topic: Optional[str] = None,
    ):
        """
        Recent publishable briefings, newest first.

        Response: { items[], count, limit, topic }
        Each item: report_date, topic, topic_id, article_count, top_story_title, generated_at
        """
        try:
            with _db_cursor() as cur:
                items = list_recent_history(cur, limit=limit, topic_name=topic)
            return {
                "items": items,
                "count": len(items),
                "limit": limit,
                "topic": topic,
            }
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/history/dates")
    def get_history_dates(
        limit: int = Query(default=90, ge=1, le=365),
        topic: Optional[str] = None,
    ):
        """
        Date index for publishable briefings.

        Without ?topic: dates[] with topics_available + total_articles per date.
        With ?topic: dates[] with article_count per date.
        Always 200; dates[] may be empty.
        """
        try:
            with _db_cursor() as cur:
                return list_briefing_dates(cur, topic_name=topic, limit=limit)
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/history/date/{report_date}")
    def get_history_for_date(report_date: str):
        """
        All publishable topic briefings for one calendar date.

        Response: { report_date, topics[], topic_count }
        404 when no publishable briefings exist for that date.
        """
        parsed = _parse_path_date(report_date)
        try:
            with _db_cursor() as cur:
                result = get_briefings_for_date(cur, parsed)
            if result["topic_count"] == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No publishable briefings found for {report_date}.",
                )
            return result
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/history/topic/{topic_name}")
    def get_history_for_topic(
        topic_name: str,
        limit: int = Query(default=90, ge=1, le=365),
    ):
        """
        Publishable briefing history for one topic, grouped by date.

        Response: { topic, topic_id, reports[], count }
        404 if topic not found or no publishable history.
        """
        try:
            with _db_cursor() as cur:
                result = get_topic_history(cur, topic_name, limit=limit)
            if result["topic_id"] is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Topic '{topic_name}' not found.",
                )
            if result["count"] == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"No publishable briefings found for topic '{topic_name}'.",
                )
            return result
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/history/search")
    def get_history_search(
        q: str = Query(..., min_length=1),
        topic: Optional[str] = None,
        limit: int = Query(default=20, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=1000),
    ):
        """
        Phase 1 keyword search (PostgreSQL ILIKE) over publishable articles.

        Response: { query, total, limit, offset, results[] }
        Always 200; total may be 0. Query param q trimmed; min 3 characters.
        """
        try:
            query = normalize_search_query(q)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            with _db_cursor() as cur:
                if topic and not get_topic_by_name(cur, topic):
                    raise HTTPException(
                        status_code=404,
                        detail=f"Topic '{topic}' not found.",
                    )
                return search_briefings(
                    cur,
                    query,
                    topic_name=topic,
                    limit=limit,
                    offset=offset,
                )
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")
