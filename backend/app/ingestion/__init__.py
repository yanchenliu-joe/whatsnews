"""
WhatsNews ingestion package.

- service.py   — DB-writing ingestion pipeline (original app/ingestion.py)
- rss.py       — fetch a feed into standardized article dicts (Phase 7.2B)
- normalize.py — convert a raw feedparser entry into a standardized dict (Phase 7.2B)

The service's public API is re-exported here so existing imports such as
`from app.ingestion import ingest_all_active_sources` keep working unchanged.
"""

from app.ingestion.service import (
    get_latest_ingestion_run,
    ingest_all_active_sources,
    ingest_sources_for_topic,
)

__all__ = [
    "get_latest_ingestion_run",
    "ingest_all_active_sources",
    "ingest_sources_for_topic",
]
