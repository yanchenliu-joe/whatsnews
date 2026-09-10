"""
Single source of truth for loading briefing data from daily_reports + articles.

Used by history APIs, export loader, and (optionally) other read paths.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.assembly import MAX_ARTICLES_PER_REPORT, compute_importance_score

MAX_ARTICLES = MAX_ARTICLES_PER_REPORT

PUBLISHABLE_WIM_WHERE = """
    a.why_it_matters IS NOT NULL AND TRIM(a.why_it_matters) != ''
"""

MAX_SEARCH_QUERY_LENGTH = 100

_ARTICLE_COLUMNS = """
    a.id,
    a.title,
    COALESCE(a.summary, '') AS summary,
    COALESCE(a.source, '') AS source,
    a.url,
    a.raw_url,
    a.published_at,
    a.why_it_matters,
    a.image_url
"""


def iso_datetime(dt: Any) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def escape_ilike(value: str) -> str:
    """Escape % and _ for safe ILIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parse_report_date(value: str) -> date:
    """Parse YYYY-MM-DD; raises ValueError on bad input."""
    return date.fromisoformat(value)


def validate_report_date(report_date: date) -> None:
    """Reject future briefing dates."""
    if report_date > date.today():
        raise ValueError("report_date cannot be in the future")


def get_latest_daily_report_date(cur) -> date | None:
    """Latest calendar date with at least one publishable daily report."""
    cur.execute(
        """
        SELECT MAX(dr.report_date) AS latest
        FROM daily_reports dr
        JOIN articles a ON a.report_id = dr.id
        WHERE a.why_it_matters IS NOT NULL AND TRIM(a.why_it_matters) != ''
        """
    )
    row = cur.fetchone()
    latest = row["latest"] if row else None
    return latest if latest else None


def normalize_search_query(query: str) -> str:
    """Trim and cap search length; raises ValueError if too short after trim."""
    q = (query or "").strip()
    if len(q) < 3:
        raise ValueError("Search query must be at least 3 characters.")
    if len(q) > MAX_SEARCH_QUERY_LENGTH:
        q = q[:MAX_SEARCH_QUERY_LENGTH]
    return q


def is_publishable_why(text: str | None) -> bool:
    return bool((text or "").strip())


def article_to_item(row: dict) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row.get("summary") or "",
        "source": row.get("source") or "",
        "url": row.get("url"),
        "why_it_matters": (row.get("why_it_matters") or "").strip(),
        "published_at": iso_datetime(row.get("published_at")),
        "image_url": row.get("image_url") or None,
    }


def report_metadata_fields(
    report_row: dict,
    article_count: int,
    *,
    topic: str | None = None,
    topic_id: int | None = None,
) -> dict[str, Any]:
    """Metadata block compatible with future headline / quality fields."""
    out: dict[str, Any] = {
        "report_date": str(report_row["report_date"]),
        "report_id": report_row["id"],
        "article_count": article_count,
        "generated_at": iso_datetime(report_row.get("created_at")),
        "headline": None,
        "summary": None,
        "quality_score": None,
        "version": None,
    }
    if topic is not None:
        out["topic"] = topic
    if topic_id is not None:
        out["topic_id"] = topic_id
    return out


def sort_articles_by_importance(articles: list[dict], topic_name: str) -> list[dict]:
    return sorted(
        articles,
        key=lambda a: compute_importance_score(
            a["title"], a.get("summary") or "", topic_name
        ),
        reverse=True,
    )


def get_active_topics(cur) -> list[dict]:
    cur.execute(
        """
        SELECT id, name, sort_order
        FROM topics
        WHERE is_active = TRUE
        ORDER BY sort_order ASC, name ASC
        """
    )
    return [dict(r) for r in cur.fetchall()]


def get_topic_by_name(cur, name: str, *, active_only: bool = False) -> dict | None:
    if active_only:
        cur.execute(
            "SELECT id, name, sort_order, is_active FROM topics WHERE name = %s AND is_active = TRUE",
            (name,),
        )
    else:
        cur.execute(
            "SELECT id, name, sort_order, is_active FROM topics WHERE name = %s",
            (name,),
        )
    row = cur.fetchone()
    return dict(row) if row else None


def find_daily_report(cur, topic_id: int, report_date: date | None = None) -> dict | None:
    """Latest report when report_date is None; exact date otherwise."""
    if report_date is not None:
        cur.execute(
            """
            SELECT id, topic_id, report_date, created_at
            FROM daily_reports
            WHERE topic_id = %s AND report_date = %s
            """,
            (topic_id, report_date),
        )
    else:
        cur.execute(
            """
            SELECT id, topic_id, report_date, created_at
            FROM daily_reports
            WHERE topic_id = %s
            ORDER BY report_date DESC
            LIMIT 1
            """,
            (topic_id,),
        )
    row = cur.fetchone()
    return dict(row) if row else None


def count_publishable_articles(cur, report_id: int) -> int:
    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM articles a
        WHERE a.report_id = %s AND {PUBLISHABLE_WIM_WHERE}
        """,
        (report_id,),
    )
    return int(cur.fetchone()["cnt"])


def is_report_publishable(cur, report_id: int) -> bool:
    return count_publishable_articles(cur, report_id) > 0


def load_articles_for_report(
    cur,
    report_id: int,
    *,
    limit: int = MAX_ARTICLES,
    publishable_only: bool = False,
) -> list[dict]:
    publishable_clause = f"AND {PUBLISHABLE_WIM_WHERE}" if publishable_only else ""
    cur.execute(
        f"""
        SELECT {_ARTICLE_COLUMNS}
        FROM articles a
        WHERE a.report_id = %s
        {publishable_clause}
        ORDER BY a.id ASC
        LIMIT %s
        """,
        (report_id, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def load_articles_for_reports_batch(
    cur,
    report_ids: list[int],
    *,
    publishable_only: bool = False,
) -> dict[int, list[dict]]:
    """Load articles for multiple reports in one query (grouped by report_id)."""
    if not report_ids:
        return {}

    publishable_clause = f"AND {PUBLISHABLE_WIM_WHERE}" if publishable_only else ""
    cur.execute(
        f"""
        SELECT a.report_id, {_ARTICLE_COLUMNS}
        FROM articles a
        WHERE a.report_id = ANY(%s)
        {publishable_clause}
        ORDER BY a.report_id ASC, a.id ASC
        """,
        (report_ids,),
    )

    grouped: dict[int, list[dict]] = {rid: [] for rid in report_ids}
    for row in cur.fetchall():
        row = dict(row)
        rid = row["report_id"]
        if rid in grouped and len(grouped[rid]) < MAX_ARTICLES:
            grouped[rid].append(row)
    return grouped


def top_story_title(articles: list[dict], topic_name: str) -> str | None:
    if not articles:
        return None
    sorted_rows = sort_articles_by_importance(articles, topic_name)
    title = (sorted_rows[0].get("title") or "").strip()
    return title or None


def build_publishable_briefing(
    cur,
    topic_row: dict,
    report_row: dict,
) -> dict[str, Any] | None:
    """Full publishable briefing for one topic + report. None if not publishable."""
    articles = load_articles_for_report(
        cur, report_row["id"], publishable_only=True
    )
    if not articles:
        return None

    topic_name = topic_row["name"]
    articles = sort_articles_by_importance(articles, topic_name)

    meta = report_metadata_fields(
        report_row,
        len(articles),
        topic=topic_name,
        topic_id=topic_row["id"],
    )
    meta["articles"] = [article_to_item(a) for a in articles]
    return meta


def list_recent_history(
    cur,
    *,
    limit: int = 30,
    topic_name: str | None = None,
) -> list[dict[str, Any]]:
    """Recent publishable briefings across topics (or one topic), newest first."""
    limit = max(1, min(limit, 365))
    topic_clause = ""
    params: list[Any] = []
    if topic_name:
        topic_clause = "AND t.name = %s"
        params.append(topic_name)

    cur.execute(
        f"""
        SELECT dr.id AS report_id,
               dr.report_date,
               dr.created_at,
               t.id AS topic_id,
               t.name AS topic,
               COUNT(a.id) AS article_count,
               (
                   SELECT a2.title
                   FROM articles a2
                   WHERE a2.report_id = dr.id
                     AND a2.why_it_matters IS NOT NULL
                     AND TRIM(a2.why_it_matters) != ''
                   ORDER BY a2.id ASC
                   LIMIT 1
               ) AS top_story_title
        FROM daily_reports dr
        JOIN topics t ON t.id = dr.topic_id
        JOIN articles a ON a.report_id = dr.id
        WHERE {PUBLISHABLE_WIM_WHERE}
        {topic_clause}
        GROUP BY dr.id, dr.report_date, dr.created_at, t.id, t.name, t.sort_order
        ORDER BY dr.report_date DESC, t.sort_order ASC, t.name ASC
        LIMIT %s
        """,
        (*params, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]

    items: list[dict[str, Any]] = []
    for row in rows:
        top_title = (row.get("top_story_title") or "").strip() or None
        items.append({
            "report_date": str(row["report_date"]),
            "topic": row["topic"],
            "topic_id": row["topic_id"],
            "report_id": row["report_id"],
            "article_count": int(row["article_count"]),
            "top_story_title": top_title,
            "generated_at": iso_datetime(row.get("created_at")),
            "headline": None,
            "summary": None,
            "quality_score": None,
            "version": None,
        })
    return items


def list_briefing_dates(
    cur,
    *,
    topic_name: str | None = None,
    limit: int = 90,
) -> dict[str, Any]:
    limit = max(1, min(limit, 365))

    if topic_name:
        topic = get_topic_by_name(cur, topic_name)
        if not topic:
            return {
                "topic": topic_name,
                "dates": [],
                "earliest": None,
                "latest": None,
                "count": 0,
            }

        cur.execute(
            f"""
            SELECT dr.report_date,
                   COUNT(a.id) AS article_count
            FROM daily_reports dr
            JOIN articles a ON a.report_id = dr.id
            WHERE dr.topic_id = %s AND {PUBLISHABLE_WIM_WHERE}
            GROUP BY dr.report_date
            ORDER BY dr.report_date DESC
            LIMIT %s
            """,
            (topic["id"], limit),
        )
        date_rows = [dict(r) for r in cur.fetchall()]
        dates = [
            {
                "date": str(r["report_date"]),
                "article_count": int(r["article_count"]),
            }
            for r in date_rows
        ]
        earliest = dates[-1]["date"] if dates else None
        latest = dates[0]["date"] if dates else None
        return {
            "topic": topic_name,
            "dates": dates,
            "earliest": earliest,
            "latest": latest,
            "count": len(dates),
        }

    cur.execute(
        f"""
        SELECT dr.report_date,
               COUNT(DISTINCT dr.topic_id) AS topics_available,
               COUNT(a.id) AS total_articles
        FROM daily_reports dr
        JOIN articles a ON a.report_id = dr.id
        WHERE {PUBLISHABLE_WIM_WHERE}
        GROUP BY dr.report_date
        ORDER BY dr.report_date DESC
        LIMIT %s
        """,
        (limit,),
    )
    date_rows = [dict(r) for r in cur.fetchall()]
    dates = [
        {
            "date": str(r["report_date"]),
            "topics_available": int(r["topics_available"]),
            "total_articles": int(r["total_articles"]),
        }
        for r in date_rows
    ]
    earliest = dates[-1]["date"] if dates else None
    latest = dates[0]["date"] if dates else None
    return {
        "topic": None,
        "dates": dates,
        "earliest": earliest,
        "latest": latest,
        "count": len(dates),
    }


def get_briefings_for_date(cur, report_date: date) -> dict[str, Any]:
    """All publishable topic briefings for a single calendar date."""
    cur.execute(
        """
        SELECT dr.id AS report_id,
               dr.report_date,
               dr.created_at,
               t.id AS topic_id,
               t.name AS topic,
               t.sort_order
        FROM daily_reports dr
        JOIN topics t ON t.id = dr.topic_id
        WHERE dr.report_date = %s
        ORDER BY t.sort_order ASC, t.name ASC
        """,
        (report_date,),
    )
    report_rows = [dict(r) for r in cur.fetchall()]
    report_ids = [r["report_id"] for r in report_rows]
    articles_by_report = load_articles_for_reports_batch(
        cur, report_ids, publishable_only=True
    )

    topics_out: list[dict[str, Any]] = []
    for report_row in report_rows:
        topic_name = report_row["topic"]
        articles = articles_by_report.get(report_row["report_id"], [])
        if not articles:
            continue
        articles = sort_articles_by_importance(articles, topic_name)
        meta = report_metadata_fields(
            {
                "id": report_row["report_id"],
                "report_date": report_row["report_date"],
                "created_at": report_row.get("created_at"),
            },
            len(articles),
            topic=topic_name,
            topic_id=report_row["topic_id"],
        )
        meta["articles"] = [article_to_item(a) for a in articles]
        topics_out.append(meta)

    return {
        "report_date": str(report_date),
        "topics": topics_out,
        "topic_count": len(topics_out),
    }


def get_topic_history(
    cur,
    topic_name: str,
    *,
    limit: int = 90,
) -> dict[str, Any]:
    limit = max(1, min(limit, 365))
    topic = get_topic_by_name(cur, topic_name)
    if not topic:
        return {
            "topic": topic_name,
            "topic_id": None,
            "reports": [],
            "count": 0,
        }

    cur.execute(
        f"""
        SELECT dr.id AS report_id,
               dr.report_date,
               dr.created_at,
               COUNT(a.id) AS article_count
        FROM daily_reports dr
        JOIN articles a ON a.report_id = dr.id
        WHERE dr.topic_id = %s AND {PUBLISHABLE_WIM_WHERE}
        GROUP BY dr.id, dr.report_date, dr.created_at
        ORDER BY dr.report_date DESC
        LIMIT %s
        """,
        (topic["id"], limit),
    )
    report_rows = [dict(r) for r in cur.fetchall()]

    reports: list[dict[str, Any]] = []
    for row in report_rows:
        articles = load_articles_for_report(
            cur, row["report_id"], publishable_only=True
        )
        articles = sort_articles_by_importance(articles, topic_name)
        reports.append({
            "report_date": str(row["report_date"]),
            "report_id": row["report_id"],
            "article_count": int(row["article_count"]),
            "top_story_title": top_story_title(articles, topic_name),
            "generated_at": iso_datetime(row.get("created_at")),
            "headline": None,
            "summary": None,
            "quality_score": None,
            "version": None,
            "articles": [article_to_item(a) for a in articles],
        })

    return {
        "topic": topic_name,
        "topic_id": topic["id"],
        "reports": reports,
        "count": len(reports),
    }


def build_search_snippet(text: str, query: str, max_len: int = 120) -> str:
    if not text:
        return ""
    lower_text = text.lower()
    lower_q = query.lower()
    idx = lower_text.find(lower_q)
    if idx < 0:
        trimmed = text[:max_len]
        return trimmed + ("..." if len(text) > max_len else "")

    start = max(0, idx - 40)
    end = min(len(text), idx + len(query) + 80)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    if len(snippet) > max_len + 10:
        snippet = snippet[:max_len] + "..."
    return snippet


def search_briefings(
    cur,
    query: str,
    *,
    topic_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    query = normalize_search_query(query)
    limit = max(1, min(limit, 50))
    offset = max(0, min(offset, 1000))

    pattern = f"%{escape_ilike(query)}%"
    topic_clause = ""
    params: list[Any] = [pattern, pattern, pattern, pattern]

    if topic_name:
        topic_clause = "AND t.name = %s"
        params.append(topic_name)

    base_where = f"""
        a.report_id IS NOT NULL
        AND {PUBLISHABLE_WIM_WHERE}
        AND (
            a.title ILIKE %s ESCAPE '\\'
            OR a.summary ILIKE %s ESCAPE '\\'
            OR a.why_it_matters ILIKE %s ESCAPE '\\'
            OR a.source ILIKE %s ESCAPE '\\'
        )
        {topic_clause}
    """

    cur.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM articles a
        JOIN daily_reports dr ON dr.id = a.report_id
        JOIN topics t ON t.id = dr.topic_id
        WHERE {base_where}
        """,
        tuple(params),
    )
    total = int(cur.fetchone()["cnt"])

    cur.execute(
        f"""
        SELECT dr.report_date,
               t.id AS topic_id,
               t.name AS topic,
               a.title,
               COALESCE(a.source, '') AS source,
               a.url,
               a.why_it_matters,
               COALESCE(a.summary, '') AS summary,
               a.image_url
        FROM articles a
        JOIN daily_reports dr ON dr.id = a.report_id
        JOIN topics t ON t.id = dr.topic_id
        WHERE {base_where}
        ORDER BY dr.report_date DESC, t.sort_order ASC, t.name ASC, a.id ASC
        LIMIT %s OFFSET %s
        """,
        (*params, limit, offset),
    )
    rows = [dict(r) for r in cur.fetchall()]

    results: list[dict[str, Any]] = []
    for row in rows:
        fields = [
            row.get("title") or "",
            row.get("summary") or "",
            row.get("why_it_matters") or "",
            row.get("source") or "",
        ]
        snippet_source = next(
            (f for f in fields if query.lower() in f.lower()),
            row.get("title") or "",
        )
        results.append({
            "report_date": str(row["report_date"]),
            "topic": row["topic"],
            "topic_id": row["topic_id"],
            "title": row["title"],
            "source": row.get("source") or "",
            "url": row.get("url"),
            "why_it_matters": (row.get("why_it_matters") or "").strip(),
            "snippet": build_search_snippet(snippet_source, query),
            "image_url": row.get("image_url") or None,
        })

    return {
        "query": query,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


def get_image_urls_by_url(conn, urls: list[str]) -> dict[str, str | None]:
    """
    Look up image_url for a list of article URLs.
    Returns a dict mapping article URL → image_url (or None if not found/null).
    Capped at 50 URLs to avoid unbounded queries.
    """
    if not urls:
        return {}
    urls = urls[:50]
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT ON (url) url, image_url
        FROM articles
        WHERE url = ANY(%s) AND image_url IS NOT NULL
        """,
        (urls,),
    )
    result = {row["url"]: row["image_url"] for row in cur.fetchall()}
    cur.close()
    return result
