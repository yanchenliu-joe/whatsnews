"""
Archive retention — deletes daily-report-scoped data older than a
configurable window (default 7 days) to keep Supabase storage bounded.

Public API:
  run_archive_cleanup(retention_days=None) -> dict
"""

from app.retention.service import run_archive_cleanup

__all__ = ["run_archive_cleanup"]
