"""
One-off cleanup for already-scraped articles.body_text rows created before
app/ingestion/scrape.py gained _strip_leading_photo_credit() (2026-07-09).

Strips a leading image caption + photo-credit line (e.g. "In this pool
photograph... | POOL/AFP via Getty Images") from already-stored body_text —
same heuristic newly-scraped articles get automatically going forward.

Safe to re-run.

Usage:
    cd backend && python3 scripts/strip_photo_credits.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.scrape import _strip_leading_photo_credit


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, body_text FROM articles WHERE body_text IS NOT NULL AND body_text != ''"
    )
    rows = cur.fetchall()

    stripped = []
    for row in rows:
        original = row["body_text"]
        text = _strip_leading_photo_credit(original).strip()
        if text != original:
            stripped.append((row["id"], text))

    print(f"[strip_photo_credits] scanned={len(rows)} to_strip={len(stripped)} dry_run={dry_run}")

    if dry_run:
        cur.close()
        conn.close()
        return

    for article_id, text in stripped:
        cur.execute("UPDATE articles SET body_text = %s WHERE id = %s", (text, article_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[strip_photo_credits] stripped={len(stripped)} rows")


if __name__ == "__main__":
    main()
