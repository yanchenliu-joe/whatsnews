"""
Archive retention cleanup — deletes daily-report-scoped data older than the
retention window (default 7 days, see config.py) from Supabase.

Five tables are date-scoped but only two of them have a real foreign key to
daily_reports (which cascades to articles, and briefing_narratives which
cascades to narrative_audio_variants) — editorial_perspectives,
editorial_watch_next, and generation_runs are linked only by matching
report_date values, with no DB-enforced reference, so each needs its own
explicit DELETE. saved_articles is deliberately never touched here: it
stores its own independent copy of article data (title/summary/source/
image_url), and its article_id foreign key is ON DELETE SET NULL, not
CASCADE — a user's bookmark survives its source article being purged.

Audio files (local disk or Supabase Storage, see audio_storage.py) are not
covered by any foreign key at all — deleting the DB row alone would leave
the actual file behind, defeating the point of this job for the Supabase
Storage case. Audio files are looked up and deleted before the DB rows that
reference them are removed, since deleting the row first would lose the
scope/report_date/version needed to reconstruct the filename.

Also cleans up stale unselected articles (report_id IS NULL) older than the
same cutoff — assembly.py's load_candidates() only ever considers a bounded,
most-recent-first pool (see FRESHNESS_WINDOW_DAYS=4 in assembly.py), so
these rows are already permanently unreachable once they age past that
window; leaving them in the table is pure storage growth with no product
value. This wasn't one of the five originally-scoped "archive" tables, but
directly serves the same "keep Supabase storage bounded" goal.

Also cleans up product_events (analytics) older than its own, separately
configured retention window (default 90 days, see
get_product_events_retention_days() — deliberately longer than the 7-day
default for the report-scoped tables above, since analytics benefits from
more history for trend analysis). Unlike the report-scoped tables,
product_events has no natural bound anywhere else in the codebase — every
INSERT via app/analytics/events.py's _record_event() just accumulates, so
this is the one table here where "no cleanup at all" was a real growth risk
found by inspection, not a known-safe simplification like saved_articles.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.database import get_connection
from app.narrative.audio_config import VOICE_PROFILES
from app.narrative.audio_storage import delete_audio_file
from app.retention.config import get_product_events_retention_days, get_retention_days


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def run_archive_cleanup(
    retention_days: int | None = None,
    product_events_retention_days: int | None = None,
) -> dict:
    """
    Delete all daily-report-scoped data with report_date older than
    (today - retention_days), plus product_events older than
    (today - product_events_retention_days) — a separate, independently
    configurable window (see module docstring for why). Returns a stats
    dict; never raises to the caller on a per-table basis — a single
    connection/transaction covers the whole run, so a failure rolls back
    everything and re-raises (the caller — the background loop or the
    admin endpoint — is responsible for catching and logging).
    """
    days = retention_days if retention_days is not None else get_retention_days()
    cutoff = date.today() - timedelta(days=days)

    events_days = (
        product_events_retention_days
        if product_events_retention_days is not None
        else get_product_events_retention_days()
    )
    events_cutoff = date.today() - timedelta(days=events_days)

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Collect audio files to delete BEFORE removing the DB rows that
        # reference them — deleting the row first loses the scope/version
        # needed to reconstruct the filename.
        cur.execute(
            "SELECT scope, report_date, version FROM briefing_narratives "
            "WHERE report_date < %s",
            (cutoff,),
        )
        narrative_rows = cur.fetchall()

        audio_deleted = 0
        audio_failed = 0
        for row in narrative_rows:
            for profile in VOICE_PROFILES:
                ok = delete_audio_file(
                    row["scope"], str(row["report_date"]), row["version"], profile
                )
                if ok:
                    audio_deleted += 1
                else:
                    audio_failed += 1

        # daily_reports cascades to articles (report_id IS NOT NULL rows).
        cur.execute("DELETE FROM daily_reports WHERE report_date < %s", (cutoff,))
        daily_reports_deleted = cur.rowcount

        # Stale unselected candidates — never reachable again, see docstring.
        cur.execute(
            "DELETE FROM articles WHERE report_id IS NULL AND "
            "COALESCE(published_at, fetched_at) < %s",
            (cutoff,),
        )
        orphan_articles_deleted = cur.rowcount

        # briefing_narratives cascades to narrative_audio_variants.
        cur.execute("DELETE FROM briefing_narratives WHERE report_date < %s", (cutoff,))
        narratives_deleted = cur.rowcount

        cur.execute("DELETE FROM editorial_perspectives WHERE report_date < %s", (cutoff,))
        perspectives_deleted = cur.rowcount

        cur.execute("DELETE FROM editorial_watch_next WHERE report_date < %s", (cutoff,))
        watch_next_deleted = cur.rowcount

        cur.execute("DELETE FROM generation_runs WHERE report_date < %s", (cutoff,))
        generation_runs_deleted = cur.rowcount

        # Own cutoff (events_cutoff), not the report-scoped one above — see
        # module docstring for why this table gets a longer default window.
        cur.execute(
            "DELETE FROM product_events WHERE created_at < %s", (events_cutoff,)
        )
        product_events_deleted = cur.rowcount

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    stats = {
        "retention_days": days,
        "cutoff_date": cutoff.isoformat(),
        "daily_reports_deleted": daily_reports_deleted,
        "orphan_articles_deleted": orphan_articles_deleted,
        "narratives_deleted": narratives_deleted,
        "perspectives_deleted": perspectives_deleted,
        "watch_next_deleted": watch_next_deleted,
        "generation_runs_deleted": generation_runs_deleted,
        "audio_files_deleted": audio_deleted,
        "audio_files_failed": audio_failed,
        "product_events_retention_days": events_days,
        "product_events_cutoff_date": events_cutoff.isoformat(),
        "product_events_deleted": product_events_deleted,
    }
    _log("archive_cleanup_completed", **stats)
    return stats
