"""
One-off backfill: re-clean already-stored articles.summary / articles.body_text
that still carry publisher-side truncation artifacts ("[...]", "Continue
reading...", WordPress's "The post X appeared first on Y." excerpt footer,
trailing "...") ingested before app/ingestion/normalize.py's
_strip_truncation_artifacts() existed.

Only updates rows where cleaning actually changes the text. Safe to re-run.

Usage:
    cd backend && python3 scripts/backfill_clean_summaries.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.normalize import _strip_truncation_artifacts


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, summary, body_text FROM articles")
    rows = cur.fetchall()

    updates = []
    for row in rows:
        new_summary = _strip_truncation_artifacts(row["summary"] or "")
        new_body = _strip_truncation_artifacts(row["body_text"] or "")
        if new_summary != (row["summary"] or "") or new_body != (row["body_text"] or ""):
            updates.append((row["id"], new_summary, new_body or None))

    print(f"[backfill] scanned={len(rows)} needing_cleanup={len(updates)} dry_run={dry_run}")

    if dry_run or not updates:
        cur.close()
        conn.close()
        return

    for article_id, new_summary, new_body in updates:
        cur.execute(
            "UPDATE articles SET summary = %s, body_text = %s WHERE id = %s",
            (new_summary, new_body, article_id),
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"[backfill] updated={len(updates)} rows")


if __name__ == "__main__":
    main()
