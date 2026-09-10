"""
One-off cleanup for articles.summary rows truncated mid-word by the old
buggy plain `[:2000]` slice in app/ingestion/service.py's
build_article_record() (fixed 2026-07-12 to use
normalize.truncate_at_word_boundary instead). Full-text scraping was
dropped the day before, so mobile's Read mode now shows *only* the
summary — a broken-looking mid-word cutoff (e.g. "...responsibility. Und")
is a real, user-visible bug, not cosmetic.

Targets rows where LENGTH(summary) is exactly 2000 (the old hard cap —
organically landing on exactly 2000 characters is effectively impossible,
so this is a reliable signal the row was cut by the bug) and the summary
doesn't already end on a clean sentence/word boundary.

Safe to re-run.

Usage:
    cd backend && python3 scripts/fix_summary_truncation.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.normalize import trim_trailing_partial_word

_CLEAN_ENDINGS = ('.', '!', '?', '"', "'", "…", "”", "’")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, summary FROM articles WHERE LENGTH(summary) = 2000")
    rows = cur.fetchall()

    changed = []
    for row in rows:
        original = row["summary"]
        if not original or original.rstrip()[-1:] in _CLEAN_ENDINGS:
            continue
        fixed = trim_trailing_partial_word(original)
        if fixed != original:
            changed.append((row["id"], fixed))

    print(
        f"[fix_summary_truncation] scanned={len(rows)} to_change={len(changed)} "
        f"dry_run={dry_run}"
    )

    if dry_run:
        cur.close()
        conn.close()
        return

    for article_id, text in changed:
        cur.execute("UPDATE articles SET summary = %s WHERE id = %s", (text, article_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[fix_summary_truncation] updated={len(changed)}")


if __name__ == "__main__":
    main()
