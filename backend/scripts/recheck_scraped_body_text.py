"""
One-off cleanup for already-scraped articles.body_text rows created before
app/ingestion/scrape.py gained _strip_leading_junk_line() and
_looks_like_navigation_dump() (2026-07-07).

For every non-empty body_text:
  - strips a leading stray short line (e.g. a photo-gallery counter)
  - if what remains still looks like a navigation/menu dump, clears
    body_text entirely (falls back to summary — a bad "success" is worse
    than a clean miss)

Safe to re-run.

Usage:
    cd backend && python3 scripts/recheck_scraped_body_text.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.scrape import _looks_like_navigation_dump, _strip_leading_junk_line


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, body_text FROM articles WHERE body_text IS NOT NULL AND body_text != ''"
    )
    rows = cur.fetchall()

    cleared = []
    stripped = []
    for row in rows:
        original = row["body_text"]
        text = _strip_leading_junk_line(original).strip()
        if _looks_like_navigation_dump(text):
            cleared.append(row["id"])
        elif text != original:
            stripped.append((row["id"], text))

    print(
        f"[recheck] scanned={len(rows)} to_clear={len(cleared)} "
        f"to_strip_only={len(stripped)} dry_run={dry_run}"
    )

    if dry_run:
        cur.close()
        conn.close()
        return

    for article_id in cleared:
        cur.execute("UPDATE articles SET body_text = NULL WHERE id = %s", (article_id,))
    for article_id, text in stripped:
        cur.execute("UPDATE articles SET body_text = %s WHERE id = %s", (text, article_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[recheck] cleared={len(cleared)} stripped={len(stripped)} rows")


if __name__ == "__main__":
    main()
