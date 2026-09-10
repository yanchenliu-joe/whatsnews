"""Load publishable briefing data for narrative generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.assembly import compute_importance_score
from app.briefing_repository import get_briefings_for_date


@dataclass
class RankedArticle:
    article_id: int
    title: str
    summary: str
    source: str
    url: str | None
    why_it_matters: str
    published_at: str | None
    topic: str
    topic_id: int
    report_id: int
    importance_score: float


def format_spoken_date(report_date: date) -> str:
    return report_date.strftime("%A, %B ") + str(report_date.day)


def load_ranked_articles(
    cur,
    report_date: date,
    *,
    max_articles: int = 10,
) -> tuple[list[RankedArticle], list[int], int]:
    """
    Load publishable articles for a date, ranked globally by importance.

    Returns (ranked_articles, source_report_ids, topic_count).
    """
    bundle = get_briefings_for_date(cur, report_date)
    topic_count = int(bundle["topic_count"])
    if topic_count == 0:
        return [], [], 0

    flat: list[RankedArticle] = []
    report_ids: list[int] = []

    for topic_row in bundle["topics"]:
        report_ids.append(topic_row["report_id"])
        topic_name = topic_row["topic"]
        for article in topic_row.get("articles") or []:
            title = article.get("title") or ""
            summary = article.get("summary") or ""
            score = compute_importance_score(title, summary, topic_name)
            flat.append(
                RankedArticle(
                    article_id=int(article.get("id") or 0),
                    title=title,
                    summary=summary,
                    source=article.get("source") or "",
                    url=article.get("url"),
                    why_it_matters=(article.get("why_it_matters") or "").strip(),
                    published_at=article.get("published_at"),
                    topic=topic_name,
                    topic_id=topic_row["topic_id"],
                    report_id=topic_row["report_id"],
                    importance_score=score,
                )
            )

    flat.sort(key=lambda a: a.importance_score, reverse=True)
    pool_count = len(flat)
    ranked = flat[:max_articles]
    return ranked, report_ids, topic_count, pool_count


def narrative_generated_at() -> str:
    return datetime.now(tz=ZoneInfo("UTC")).isoformat()
