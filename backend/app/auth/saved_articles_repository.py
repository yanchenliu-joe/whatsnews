"""Saved articles persistence (Phase 18.3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

import psycopg2

from app.database import get_connection


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "article_id": row.get("article_id"),
        "article_url": row["article_url"],
        "article_title": row.get("article_title"),
        "topic": row.get("topic"),
        "source": row.get("source"),
        "summary": row.get("summary"),
        "why_it_matters": row.get("why_it_matters"),
        "image_url": row.get("image_url") or None,
        "saved_at": row["saved_at"].isoformat() if row.get("saved_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def _lookup_article_id(cur, article_url: str) -> int | None:
    cur.execute(
        """
        SELECT id
        FROM articles
        WHERE url = %s OR raw_url = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (article_url, article_url),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def list_saved_articles(user_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT sa.id, sa.article_id, sa.article_url, sa.article_title,
                   sa.topic, sa.source, sa.summary, sa.why_it_matters,
                   COALESCE(sa.image_url, a.image_url) AS image_url,
                   sa.saved_at, sa.created_at
            FROM saved_articles sa
            LEFT JOIN articles a ON a.id = sa.article_id
            WHERE sa.user_id = %s
            ORDER BY sa.saved_at DESC, sa.id DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        cur.close()
        return [_row_to_dict(dict(row)) for row in rows]
    except psycopg2.Error as e:
        raise RuntimeError(f"Saved articles database error: {e}") from e
    finally:
        conn.close()


def upsert_saved_article(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    article_url = str(payload["article_url"]).strip()
    if not article_url:
        raise ValueError("article_url is required.")

    article_id = payload.get("article_id")
    if article_id is not None:
        article_id = int(article_id)

    saved_at = payload.get("saved_at")
    if isinstance(saved_at, str):
        saved_at = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
    elif saved_at is None:
        saved_at = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        cur = conn.cursor()

        if article_id is None:
            article_id = _lookup_article_id(cur, article_url)

        cur.execute(
            """
            INSERT INTO saved_articles (
                user_id, article_id, article_url, article_title, topic, source,
                summary, why_it_matters, image_url, saved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, article_url) DO UPDATE SET
                article_id = COALESCE(EXCLUDED.article_id, saved_articles.article_id),
                article_title = COALESCE(EXCLUDED.article_title, saved_articles.article_title),
                topic = COALESCE(EXCLUDED.topic, saved_articles.topic),
                source = COALESCE(EXCLUDED.source, saved_articles.source),
                summary = COALESCE(EXCLUDED.summary, saved_articles.summary),
                why_it_matters = COALESCE(EXCLUDED.why_it_matters, saved_articles.why_it_matters),
                image_url = COALESCE(EXCLUDED.image_url, saved_articles.image_url),
                saved_at = GREATEST(saved_articles.saved_at, EXCLUDED.saved_at)
            RETURNING id, article_id, article_url, article_title, topic, source,
                      summary, why_it_matters, image_url, saved_at, created_at
            """,
            (
                user_id,
                article_id,
                article_url,
                payload.get("article_title"),
                payload.get("topic"),
                payload.get("source"),
                payload.get("summary"),
                payload.get("why_it_matters"),
                payload.get("image_url"),
                saved_at,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f"Saved articles database error: {e}") from e
    finally:
        conn.close()

    if not row:
        raise RuntimeError("Saved article upsert returned no row.")

    return _row_to_dict(dict(row))


def delete_saved_article(user_id: str, identifier: str) -> bool:
    decoded = unquote(identifier).strip()
    if not decoded:
        return False

    conn = get_connection()
    try:
        cur = conn.cursor()
        deleted = False

        if decoded.isdigit():
            numeric_id = int(decoded)
            cur.execute(
                """
                DELETE FROM saved_articles
                WHERE user_id = %s AND id = %s
                """,
                (user_id, numeric_id),
            )
            deleted = cur.rowcount > 0

            if not deleted:
                cur.execute(
                    """
                    DELETE FROM saved_articles
                    WHERE user_id = %s AND article_id = %s
                    """,
                    (user_id, numeric_id),
                )
                deleted = cur.rowcount > 0

        if not deleted:
            cur.execute(
                """
                DELETE FROM saved_articles
                WHERE user_id = %s AND article_url = %s
                """,
                (user_id, decoded),
            )
            deleted = cur.rowcount > 0

        conn.commit()
        cur.close()
        return deleted
    except psycopg2.Error as e:
        conn.rollback()
        raise RuntimeError(f"Saved articles database error: {e}") from e
    finally:
        conn.close()
