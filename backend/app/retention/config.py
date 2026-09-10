"""Archive retention configuration."""

from __future__ import annotations

import os

DEFAULT_RETENTION_DAYS = 7
DEFAULT_CLEANUP_TICK_SECONDS = 86400  # 24h

# product_events (analytics) is not daily-report-scoped like the other five
# tables this job cleans up, and has no natural "already unreachable" bound
# the way stale unselected articles do (see run_archive_cleanup's docstring)
# — it grows purely with user activity, with no cap anywhere else in the
# codebase. 90 days (vs. 7 for the report-scoped tables) keeps enough
# history for monthly trend analysis while still bounding growth.
DEFAULT_PRODUCT_EVENTS_RETENTION_DAYS = 90


def get_retention_days() -> int:
    return int(os.getenv("ARCHIVE_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))


def get_cleanup_tick_seconds() -> int:
    return int(os.getenv("ARCHIVE_CLEANUP_TICK_SECONDS", str(DEFAULT_CLEANUP_TICK_SECONDS)))


def get_product_events_retention_days() -> int:
    return int(
        os.getenv(
            "PRODUCT_EVENTS_RETENTION_DAYS", str(DEFAULT_PRODUCT_EVENTS_RETENTION_DAYS)
        )
    )
