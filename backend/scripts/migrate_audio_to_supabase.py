"""
One-off migration: upload every existing local media/audio/*.mp3 file to the
Supabase Storage "narrative-audio" bucket (migration 0026), then update the
corresponding narrative_audio_variants row's audio_url/audio_storage_path to
point at the new Storage URL.

Prerequisites: VOICE_AUDIO_STORAGE=supabase and SUPABASE_SERVICE_ROLE_KEY
must already be set in .env (this script reads them the same way the app
does, via app.narrative.audio_storage).

Idempotent — re-running just re-uploads (x-upsert) and re-points already-
migrated rows to the same URL.

Usage:
    cd backend && python3 scripts/migrate_audio_to_supabase.py [--dry-run]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_connection
from app.narrative.audio_config import get_local_audio_dir
from app.narrative.audio_storage import _upload_to_supabase_storage, build_public_url


def _parse_filename(filename: str) -> tuple[str, str, int, str] | None:
    """'{report_date}_{scope}_v{version}_{voice_profile}.mp3' -> parts, or None."""
    stem = filename[:-4] if filename.endswith(".mp3") else filename
    try:
        date_part, rest = stem.split("_", 1)
        scope, rest = rest.rsplit("_v", 1)
        version_str, voice_profile = rest.split("_", 1)
        return date_part, scope, int(version_str), voice_profile
    except ValueError:
        return None


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    audio_dir = get_local_audio_dir()
    mp3_files = sorted(audio_dir.rglob("*.mp3"))  # recursive — some legacy files live in subdirs
    print(f"[migrate] found {len(mp3_files)} local audio files in {audio_dir}")

    conn = get_connection()
    cur = conn.cursor()

    uploaded = 0
    db_updated = 0
    skipped = []

    for mp3_path in mp3_files:
        parsed = _parse_filename(mp3_path.name)
        if not parsed:
            skipped.append(mp3_path.name)
            continue
        report_date, scope, version, voice_profile = parsed

        if not dry_run:
            data = mp3_path.read_bytes()
            _upload_to_supabase_storage(mp3_path.name, data)
        uploaded += 1

        new_url = build_public_url(scope, report_date, version, voice_profile)
        if not dry_run:
            cur.execute(
                """
                UPDATE narrative_audio_variants nav
                SET audio_url = %s, audio_storage_path = %s
                FROM briefing_narratives bn
                WHERE nav.narrative_id = bn.id
                  AND bn.report_date = %s
                  AND bn.scope = %s
                  AND bn.version = %s
                  AND nav.voice_profile = %s
                """,
                (new_url, mp3_path.name, report_date, scope, version, voice_profile),
            )
            db_updated += cur.rowcount
            # Some older rows may store audio_url/audio_storage_path directly
            # on briefing_narratives rather than a narrative_audio_variants
            # row (pre-Phase-14.7 single-voice schema) — update those too.
            cur.execute(
                """
                UPDATE briefing_narratives
                SET audio_url = %s, audio_storage_path = %s
                WHERE report_date = %s AND scope = %s AND version = %s
                  AND audio_storage_path LIKE %s
                """,
                (new_url, mp3_path.name, report_date, scope, version, f"%{mp3_path.name}"),
            )
            db_updated += cur.rowcount

    if not dry_run:
        conn.commit()
    cur.close()
    conn.close()

    print(
        f"[migrate] uploaded={uploaded} db_rows_updated={db_updated} "
        f"skipped_unparseable={len(skipped)} dry_run={dry_run}"
    )
    if skipped:
        print("[migrate] skipped filenames:", skipped)


if __name__ == "__main__":
    main()
