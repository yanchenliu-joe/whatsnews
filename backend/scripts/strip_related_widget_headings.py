"""
One-off cleanup for Technical Debt #23 (resolved 2026-07-13): mid-article
"related content" widgets (Variety's "Popular on Variety", Deadline's
"Watch on Deadline", Barchart's "More News from Barchart", Al Jazeera's
"Recommended Stories" list widget) that trafilatura spliced into scraped
body_text — and, via improve_summary_from_body()'s extraction, sometimes
into summary too.

Applies app/ingestion/scrape.py's _strip_related_widget_headings() and
_strip_al_jazeera_recommended_stories() directly to both columns. These
are pure text-transformation functions with no dependency on which code
path produced the text, so it's safe to reuse them here rather than
duplicate the same patterns into normalize.py's summary-cleaning path.

Safe to re-run — only rewrites rows where a marker is actually still
present.

**Fallback for truncated-mid-widget summaries**: the Al Jazeera widget's
strict N-entry matcher correctly declines to touch a `summary` where the
widget's list got cut short by the normal summary-length cap (found
2026-07-13 — 57 real rows had a clean body_text but a truncated widget
still sitting in `summary`, e.g. "...- list 2 of 4Why have half a
million..." with no further entries). For any row where direct cleaning
still leaves a marker in `summary` but `body_text` is already clean,
falls back to fully re-deriving `summary` via
`extract_summary_from_body(body_text)` instead of patching the truncated
text in place.

Usage:
    cd backend && python3 scripts/strip_related_widget_headings.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.ingestion.normalize import extract_summary_from_body
from app.ingestion.scrape import (
    _strip_al_jazeera_recommended_stories,
    _strip_related_widget_headings,
)

_MARKERS = (
    "Popular on Variety",
    "Watch on Deadline",
    "More News from Barchart",
    "Recommended Stories",
)


def _clean(text: str) -> str:
    text = _strip_al_jazeera_recommended_stories(text)
    text = _strip_related_widget_headings(text)
    return text


def _has_marker(text: str) -> bool:
    return any(m in text for m in _MARKERS)


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    conn = get_connection()
    cur = conn.cursor()
    where = " OR ".join([f"body_text ILIKE %s OR summary ILIKE %s"] * len(_MARKERS))
    params = tuple(param for m in _MARKERS for param in (f"%{m}%", f"%{m}%"))
    cur.execute(f"SELECT id, body_text, summary FROM articles WHERE {where}", params)
    rows = cur.fetchall()

    changed = []
    regenerated = 0
    for row in rows:
        original_body = row["body_text"] or ""
        original_summary = row["summary"] or ""
        new_body = _clean(original_body)
        new_summary = _clean(original_summary)

        if _has_marker(new_summary) and not _has_marker(new_body):
            new_summary = extract_summary_from_body(new_body) or new_summary
            regenerated += 1

        if new_body != original_body or new_summary != original_summary:
            changed.append((row["id"], new_body, new_summary))

    print(
        f"[strip_related_widget_headings] scanned={len(rows)} to_change={len(changed)} "
        f"regenerated_from_body={regenerated} dry_run={dry_run}"
    )
    for article_id, _, _ in changed[:10]:
        print(f"  id={article_id}")

    if dry_run:
        cur.close()
        conn.close()
        return

    for article_id, new_body, new_summary in changed:
        cur.execute(
            "UPDATE articles SET body_text = %s, summary = %s WHERE id = %s",
            (new_body, new_summary, article_id),
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"[strip_related_widget_headings] updated={len(changed)}")


if __name__ == "__main__":
    main()
