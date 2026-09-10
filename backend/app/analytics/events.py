"""Product event tracking (POST /events allow-list + insert helper)."""

from __future__ import annotations

from typing import Optional

from app.database import get_connection
from app.log_utils import _log

VALID_EVENT_NAMES = frozenset({
    "push_sent",
    "article_opened",
    "article_saved",
    "briefing_refreshed",
    "briefing_archive_viewed",
    "briefing_date_changed",
    "history_search_submitted",
    "history_search_result_opened",
    "voice_card_seen",
    "voice_play_started",
    "voice_paused",
    "voice_play_failed",
    "voice_history_card_seen",
    "voice_history_play_started",
    "voice_history_play_failed",
    # Onboarding
    "onboarding_completed",
    # Paywall / subscription
    "paywall_viewed",
    "paywall_dismissed",
    "paywall_converted",
    # Engagement
    "streak_milestone",
    "article_shared",
    "article_saved_pdf",
    "briefing_shared_pdf",
    # Related articles (Phase 31)
    "related_article_opened",
    # Streak tab (Phase 35)
    "streak_tab_viewed",
    "streak_shared",
    # Badge sharing (2026-07-12)
    "badge_shared",
})


def _record_event(
    event_name: str,
    article_id: Optional[int] = None,
    topic_name: Optional[str] = None,
    metadata_text: Optional[str] = None,
) -> None:
    """
    Insert a row into product_events.  Never raises — failures are logged
    and silently swallowed so callers (scheduler, endpoints) stay stable.
    """
    try:
        conn = get_connection()
    except ValueError:
        return

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO product_events (event_name, article_id, topic_name, metadata_text)
            VALUES (%s, %s, %s, %s)
            """,
            (event_name, article_id, topic_name, metadata_text),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        _log("event_record_failed", event=event_name, error=str(e)[:200])
