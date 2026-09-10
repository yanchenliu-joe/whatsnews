"""Persist editorial_metadata JSONB on articles."""

from __future__ import annotations

import json

from psycopg2.extras import execute_values


def persist_article_profiles(cur, profiles: dict[int, dict]) -> int:
    """
    Write editorial_metadata for each article id in one batch.
    Returns number of rows updated.
    Skips gracefully if the column does not exist yet.
    """
    if not profiles:
        return 0

    rows = [
        (article_id, json.dumps(profile))
        for article_id, profile in profiles.items()
    ]

    try:
        execute_values(
            cur,
            """
            UPDATE articles AS a
            SET editorial_metadata = v.metadata::jsonb
            FROM (VALUES %s) AS v(id, metadata)
            WHERE a.id = v.id::integer
            """,
            rows,
            template="(%s, %s)",
        )
        return cur.rowcount
    except Exception as exc:
        if _is_missing_column_error(exc):
            raise EditorialMetadataColumnMissing() from exc
        raise


class EditorialMetadataColumnMissing(Exception):
    """Raised when articles.editorial_metadata column is not migrated yet."""


def _is_missing_column_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "editorial_metadata" in msg and (
        "does not exist" in msg or "undefined column" in msg
    )
