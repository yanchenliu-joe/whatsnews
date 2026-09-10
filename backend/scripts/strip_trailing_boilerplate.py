"""
One-off cleanup for already-scraped articles.body_text rows created before
app/ingestion/scrape.py gained _truncate_at_trailing_boilerplate() and
_strip_zdnet_leading_disclosure() (2026-07-10).

Truncates trailing boilerplate footers (newsletter prompts, wire-service
attributions, disclosure lines) and strips ZDNET's leading "why trust us"
disclosure block — same heuristics newly-scraped articles get automatically
going forward.

Safe to re-run.

Usage:
    cd backend && python3 scripts/strip_trailing_boilerplate.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.scrape import (
    _strip_zdnet_leading_disclosure,
    _truncate_at_trailing_boilerplate,
)


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, body_text FROM articles WHERE body_text IS NOT NULL AND body_text != ''"
    )
    rows = cur.fetchall()

    changed = []
    for row in rows:
        original = row["body_text"]
        text = _strip_zdnet_leading_disclosure(original)
        text = _truncate_at_trailing_boilerplate(text).strip()
        if text != original:
            changed.append((row["id"], text))

    print(
        f"[strip_trailing_boilerplate] scanned={len(rows)} to_change={len(changed)} "
        f"dry_run={dry_run}"
    )

    if dry_run:
        cur.close()
        conn.close()
        return

    for article_id, text in changed:
        cur.execute("UPDATE articles SET body_text = %s WHERE id = %s", (text, article_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[strip_trailing_boilerplate] changed={len(changed)} rows")


if __name__ == "__main__":
    main()
