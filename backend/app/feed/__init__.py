"""
WhatsNews Unified Feed Layer (Phase 28).

Single product-facing entry point that routes to the appropriate
intelligence depth based on the requested mode.

  GET /daily-feed?topic=AI&mode=auto

Public API:
  get_daily_feed(topic, mode, report_date) → dict
"""

from app.feed.service import get_daily_feed, get_auto_feed, VALID_MODES

__all__ = ["get_daily_feed", "get_auto_feed", "VALID_MODES"]
