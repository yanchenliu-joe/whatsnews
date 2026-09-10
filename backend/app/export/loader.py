"""Load assembled daily reports for export with quality gating."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.assembly import MAX_ARTICLES_PER_REPORT
from app.briefing_repository import (
    find_daily_report,
    get_active_topics,
    get_topic_by_name,
    iso_datetime,
    load_articles_for_report,
    sort_articles_by_importance,
)
from app.export.models import ExportArticle, ExportBundle, ExportQualityError, ExportTopic

MAX_ARTICLES = MAX_ARTICLES_PER_REPORT


def load_exportable_briefing(
    cur,
    *,
    export_date: date | None = None,
    topic_name: str | None = None,
) -> ExportBundle:
    """
    Build an ExportBundle from assembled daily reports.

    Only articles linked to daily_reports via report_id are included.
    Raises ExportQualityError when any included article lacks why_it_matters.
    Under-filled topics (< MAX_ARTICLES) produce warnings but do not block export.

    - export_date set: load reports for that exact date per topic.
    - export_date None: load the latest report per topic (report_date DESC).
    - topic_name set: restrict to a single topic (404-style error if missing).
    """
    if topic_name:
        topic_row = get_topic_by_name(cur, topic_name, active_only=True)
        if not topic_row:
            raise ExportQualityError(
                f"Topic '{topic_name}' not found or not active.",
                {"topic": topic_name},
            )
        topic_rows = [topic_row]
    else:
        topic_rows = get_active_topics(cur)

    warnings: list[str] = []
    topics_out: list[ExportTopic] = []
    missing_why: list[dict[str, str]] = []
    report_dates: list[str] = []

    for topic_row in topic_rows:
        tid = topic_row["id"]
        tname = topic_row["name"]

        report = find_daily_report(cur, tid, export_date)
        if not report:
            if topic_name:
                raise ExportQualityError(
                    f"No daily report found for topic '{tname}'"
                    + (f" on {export_date}" if export_date else ""),
                    {"topic": tname, "export_date": str(export_date) if export_date else None},
                )
            warnings.append(f"{tname}: no report found, skipped")
            continue

        report_id = report["id"]
        report_date_str = str(report["report_date"])
        report_dates.append(report_date_str)

        rows = load_articles_for_report(cur, report_id, limit=MAX_ARTICLES)

        if not rows:
            if topic_name:
                raise ExportQualityError(
                    f"No assembled articles for topic '{tname}' on {report_date_str}.",
                    {"topic": tname, "report_date": report_date_str},
                )
            warnings.append(f"{tname}: report has no articles, skipped")
            continue

        for row in rows:
            wim = (row.get("why_it_matters") or "").strip()
            if not wim:
                missing_why.append({
                    "topic": tname,
                    "title": row.get("title") or "",
                    "report_date": report_date_str,
                })

        if len(rows) < MAX_ARTICLES:
            warnings.append(
                f"{tname}: {len(rows)}/{MAX_ARTICLES} articles (under-filled)"
            )

        rows = sort_articles_by_importance(rows, tname)

        articles = [
            ExportArticle(
                position=i + 1,
                title=r["title"],
                source=r["source"],
                url=r.get("url"),
                raw_url=r.get("raw_url"),
                published_at=iso_datetime(r.get("published_at")),
                summary=r.get("summary") or "",
                why_it_matters=(r.get("why_it_matters") or "").strip(),
            )
            for i, r in enumerate(rows)
        ]

        topics_out.append(
            ExportTopic(
                topic=tname,
                report_date=report_date_str,
                report_id=report_id,
                article_count=len(articles),
                articles=articles,
            )
        )

    if missing_why:
        raise ExportQualityError(
            "Export blocked: one or more articles are missing why_it_matters.",
            {"missing_why_it_matters": missing_why},
        )

    if topic_name and not topics_out:
        raise ExportQualityError(
            f"No exportable report for topic '{topic_name}'.",
            {"topic": topic_name},
        )

    if not topics_out:
        raise ExportQualityError(
            "No exportable reports found for any active topic.",
            {"warnings": warnings},
        )

    if export_date is not None:
        resolved_export_date = str(export_date)
    elif report_dates:
        resolved_export_date = max(report_dates)
    else:
        resolved_export_date = str(date.today())

    generated_at = datetime.now(tz=ZoneInfo("UTC")).isoformat()

    return ExportBundle(
        export_date=resolved_export_date,
        generated_at=generated_at,
        quality_gate={
            "passed": True,
            "warnings": warnings,
        },
        topics=topics_out,
    )


def load_exportable_briefing_from_connection(
    conn,
    *,
    export_date: date | None = None,
    topic_name: str | None = None,
) -> ExportBundle:
    cur = conn.cursor()
    try:
        return load_exportable_briefing(
            cur,
            export_date=export_date,
            topic_name=topic_name,
        )
    finally:
        cur.close()
