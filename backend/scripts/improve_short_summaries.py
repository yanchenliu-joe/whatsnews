"""
One-off backfill: regenerates `articles.summary` from already-stored
`body_text` — both (a) lengthening summaries too short to serve as the
article's primary (and, since full-text scraping was dropped from Read
mode 2026-07-11, ONLY) content shown to users, and (b) boilerplate-
cleaning summaries that are already long enough but still carry site
junk (ads/newsletter-CTA/nav-dump text — see improve_summary_from_body()'s
2026-07-13 update). Purely rule-based, no AI — extracts/cleans, never
rewrites or invents text.

Most rows already have real, cleaned body_text sitting in the DB from
when ENABLE_ARTICLE_SCRAPING was briefly on (2026-07-07 to 07-11) — this
script is what actually puts that leftover data to use, at zero new
scraping cost. Going forward, new ingestion (service.py's
build_article_record()/_persist_topic_fetch_results()) already improves
summaries automatically; this script only backfills already-ingested rows.

Deliberately scans ALL rows with body_text (not just short summaries) as
of 2026-07-13 — the junk-cleaning pass needs to reach already-long
summaries too, since a summary can be "long enough" and still be
polluted (found from real IndieWire/Hypebeast/CNBC/etc. rows whose RSS
summary field already embedded full article text, boilerplate included).

Safe to re-run — only rewrites rows where improve_summary_from_body()
actually produces a different (longer or cleaner) summary than what's stored.

Usage:
    cd backend && python3 scripts/improve_short_summaries.py [--dry-run] [--days=30]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.normalize import improve_summary_from_body


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    days = 30
    for arg in sys.argv[1:]:
        if arg.startswith("--days="):
            days = int(arg.split("=", 1)[1])

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, summary, body_text
        FROM articles
        WHERE body_text IS NOT NULL AND body_text != ''
          AND fetched_at >= NOW() - (%s || ' days')::interval
        """,
        (days,),
    )
    rows = cur.fetchall()

    changed = []
    for row in rows:
        improved = improve_summary_from_body(row["summary"] or "", row["body_text"])
        if improved != (row["summary"] or ""):
            changed.append((row["id"], improved, len(row["summary"] or ""), len(improved)))

    print(
        f"[improve_short_summaries] scanned={len(rows)} to_change={len(changed)} "
        f"days={days} dry_run={dry_run}"
    )
    for article_id, _, old_len, new_len in changed[:10]:
        print(f"  id={article_id} {old_len} -> {new_len} chars")

    if dry_run:
        cur.close()
        conn.close()
        return

    for article_id, text, _, _ in changed:
        cur.execute("UPDATE articles SET summary = %s WHERE id = %s", (text, article_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"[improve_short_summaries] updated={len(changed)}")


if __name__ == "__main__":
    main()
