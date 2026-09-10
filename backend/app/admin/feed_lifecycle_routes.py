"""Admin feed lifecycle mutation routes (test/disable/enable/pause/promote/replace-mark)."""

from __future__ import annotations

import time
from typing import Optional

import psycopg2
from fastapi import FastAPI, Header, HTTPException

from app.database import get_connection
from app.ingestion.rss import fetch_rss_feed_result
from app.log_utils import _log


def register_admin_feed_lifecycle_routes(app: FastAPI, require_admin_key) -> None:
    """Attach /admin/feeds/{feed_id}/* endpoints. require_admin_key is app.admin.deps.require_admin_key."""

    @app.post("/admin/feeds/{feed_id}/test")
    def admin_feed_test(feed_id: int, x_admin_key: Optional[str] = Header(default=None)):
        """
        Fetch a single RSS feed and return a connectivity report. Does NOT persist articles.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name, feed_url, is_active FROM news_sources WHERE id = %s",
                (feed_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        if not row:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")

        fetch_started = time.time()
        result = fetch_rss_feed_result(row["feed_url"], max_items=20)
        fetch_ms = int((time.time() - fetch_started) * 1000)

        return {
            "feed_id": feed_id,
            "feed_name": row["name"],
            "feed_url": row["feed_url"],
            "is_active": row["is_active"],
            "success": result.status == "ok",
            "article_count": len(result.articles) if result.articles else 0,
            "fetch_time_ms": fetch_ms,
            "error": result.error,
        }

    @app.post("/admin/feeds/{feed_id}/disable")
    def admin_feed_disable(feed_id: int, x_admin_key: Optional[str] = Header(default=None)):
        """Manually disable a feed (sets is_active = FALSE)."""
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE news_sources SET is_active = FALSE WHERE id = %s RETURNING id, name",
                (feed_id,),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        if not row:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")
        return {"feed_id": row["id"], "feed_name": row["name"], "is_active": False}

    @app.post("/admin/feeds/{feed_id}/enable")
    def admin_feed_enable(feed_id: int, x_admin_key: Optional[str] = Header(default=None)):
        """Manually re-enable a feed (sets is_active = TRUE, clears auto_disabled_at)."""
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE news_sources
                SET is_active = TRUE, auto_disabled_at = NULL, consecutive_failures = 0
                WHERE id = %s
                RETURNING id, name
                """,
                (feed_id,),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        if not row:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")
        return {"feed_id": row["id"], "feed_name": row["name"], "is_active": True}

    @app.post("/admin/feeds/{feed_id}/pause")
    def admin_feed_pause(feed_id: int, x_admin_key: Optional[str] = Header(default=None)):
        """
        Pause a feed: set feed_state = 'paused'.
        Paused feeds are excluded from all automatic ingestion runs.
        Use /enable to resume.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE news_sources
                SET feed_state = 'paused', skip_next_run = FALSE
                WHERE id = %s AND is_active = TRUE
                RETURNING id, name, feed_state
                """,
                (feed_id,),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")
        if not row:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found or already inactive")
        return {"feed_id": row["id"], "feed_name": row["name"], "feed_state": row["feed_state"]}

    @app.post("/admin/feeds/{feed_id}/promote")
    def admin_feed_promote(feed_id: int, x_admin_key: Optional[str] = Header(default=None)):
        """
        Promote a feed back to 'active': clears paused/degraded state and resets throttling flags.
        """
        require_admin_key(x_admin_key)
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE news_sources
                SET feed_state           = 'active',
                    skip_next_run        = FALSE,
                    consecutive_failures = 0,
                    is_active            = TRUE,
                    auto_disabled_at     = NULL
                WHERE id = %s
                RETURNING id, name, feed_state
                """,
                (feed_id,),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")
        if not row:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")
        return {"feed_id": row["id"], "feed_name": row["name"], "feed_state": row["feed_state"]}

    @app.post("/admin/feeds/{feed_id}/replace-mark")
    def admin_feed_replace_mark(
        feed_id: int,
        body: dict,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Mark a feed as a replacement candidate.
        Body: { "reason": "...", "clear": false }  # clear=true removes the flag
        """
        require_admin_key(x_admin_key)
        clear = body.get("clear", False)
        reason = (body.get("reason") or "").strip() or None
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")
        try:
            cur = conn.cursor()
            if clear:
                cur.execute(
                    "UPDATE news_sources SET replace_flag = FALSE, replace_reason = NULL WHERE id = %s RETURNING id, name",
                    (feed_id,),
                )
            else:
                cur.execute(
                    "UPDATE news_sources SET replace_flag = TRUE, replace_reason = %s WHERE id = %s RETURNING id, name",
                    (reason, feed_id),
                )
            row = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")
        if not row:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")
        return {
            "feed_id": row["id"],
            "feed_name": row["name"],
            "replace_flag": not clear,
            "replace_reason": reason if not clear else None,
        }
