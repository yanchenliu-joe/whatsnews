"""Related articles DB access (Phase 31). Read-only candidate pool query."""

from __future__ import annotations

from typing import Any, Optional

from app.database import get_connection


def fetch_candidate_articles(
    exclude_url: Optional[str],
    days: int,
    pool_limit: int,
) -> list[dict[str, Any]]:
    """
    Candidate pool: articles from active-topic reports in the last `days`
    days, most recent first, capped at `pool_limit` rows. Scoring/ranking
    happens in Python (matching.py) after this — this is deliberately a
    cheap, unfiltered fetch.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT a.id, a.title, a.summary, a.why_it_matters, a.source, a.url,
                   a.published_at, a.image_url, t.name AS topic_name
            FROM articles a
            JOIN daily_reports dr ON a.report_id = dr.id
            JOIN topics t ON dr.topic_id = t.id
            WHERE dr.report_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
              AND t.is_active = TRUE
              AND (%s::text IS NULL OR a.url != %s)
            ORDER BY a.published_at DESC NULLS LAST
            LIMIT %s
            """,
            (exclude_url, exclude_url, pool_limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        conn.close()
