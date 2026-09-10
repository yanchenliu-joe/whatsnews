"""Load articles with editorial metadata for perspective generation."""

from __future__ import annotations

import json
from datetime import date

from app.perspective.models import PerspectiveArticle


def _parse_metadata(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def load_perspective_articles(cur, report_date: date) -> tuple[list[PerspectiveArticle], int]:
    """
    Load publishable articles for a date, ranked by editorial importance_score.

    Returns (articles, topic_count).
    """
    cur.execute(
        """
        SELECT
            a.id,
            a.title,
            COALESCE(a.summary, '') AS summary,
            COALESCE(a.source, '') AS source,
            COALESCE(a.why_it_matters, '') AS why_it_matters,
            a.editorial_metadata,
            t.name AS topic
        FROM articles a
        JOIN daily_reports dr ON dr.id = a.report_id
        JOIN topics t ON t.id = dr.topic_id
        WHERE dr.report_date = %s
          AND a.why_it_matters IS NOT NULL
          AND TRIM(a.why_it_matters) != ''
        ORDER BY t.sort_order ASC, t.name ASC, a.id ASC
        """,
        (report_date,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    topics_seen: set[str] = set()
    articles: list[PerspectiveArticle] = []

    for row in rows:
        meta = _parse_metadata(row.get("editorial_metadata"))
        wim_meta = meta.get("wim") if isinstance(meta.get("wim"), dict) else {}
        importance = int(meta.get("importance_score") or 0)
        topics_seen.add(row["topic"])
        articles.append(
            PerspectiveArticle(
                article_id=row["id"],
                title=row["title"],
                summary=row["summary"],
                source=row["source"],
                topic=row["topic"],
                why_it_matters=row["why_it_matters"],
                importance_score=importance,
                impact_types=list(meta.get("impact_types") or []),
                editorial_tags=list(meta.get("editorial_tags") or []),
                cross_topic_candidates=list(meta.get("cross_topic_candidates") or []),
                watch_next=str(wim_meta.get("watch_next") or ""),
            )
        )

    articles.sort(key=lambda a: a.importance_score, reverse=True)
    return articles, len(topics_seen)
