# Phase 15.1 — RSS Concurrent Ingestion

**Status:** complete  
**Last updated:** 2026-06-26

## Goal

Reduce pipeline ingest stage runtime by fetching RSS feeds concurrently with per-feed timeouts and isolated error handling.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `INGESTION_MAX_CONCURRENCY` | `8` | Max parallel RSS fetches |
| `INGESTION_FEED_TIMEOUT_SECONDS` | `10` | Per-feed HTTP timeout (seconds) |
| `INGESTION_SLOW_SOURCE_THRESHOLD_SECONDS` | `5` | Include in `slow_sources` when duration ≥ threshold or fetch failed |
| `INGESTION_TOPIC_CONCURRENCY` | `4` (or `min(4, max_concurrency)`) | Parallel topic DB persist workers after global fetch |

## Architecture

```
Load all sources → global concurrent HTTP fetch (max 8) → parallel per-topic DB persist (max 4)
```

Per-topic admin path (`ingest_sources_for_topic`) still fetches concurrently then writes sequentially on one connection.

## Pipeline response fields (ingest)

Existing fields preserved: `topics_processed`, `sources_processed`, `sources_checked`, `articles_inserted`, `errors_count`, `topic_seconds`.

Added/enhanced:

- `duration_seconds` — total ingest wall time
- `fetch_phase_seconds` — global RSS fetch phase
- `persist_phase_seconds` — parallel DB persist phase
- `source_timings[]` — per-source metrics including `feed_url`, `status`, `duration_seconds`
- `slow_sources[]` — feeds over threshold or failed (`topic`, `source`, `feed_url`, `duration_seconds`, `status`, `error`)

## Phase 15.2 — Batch DB persist

| Variable | Default | Purpose |
|----------|---------|---------|
| `INGESTION_DB_BATCH_SIZE` | `100` | Rows per `execute_values` insert batch |

- Prefetch existing `content_hash` values per topic before insert (skips duplicate round-trips on repeat runs).
- Batch insert via `psycopg2.extras.execute_values` with `ON CONFLICT DO NOTHING RETURNING id`.
- Batch failure falls back to per-row insert for that batch only.

Additional ingest response fields: `build_records_seconds`, `db_insert_seconds`, `duplicate_skip_count`, `batch_count`.

## Verification

```bash
curl -X POST http://localhost:8000/admin/run-pipeline \
  -H "X-Admin-Key: whatsnews-dev-key" \
  | jq '{timing_seconds, ingest: {duration_seconds, slow_sources, topic_seconds}}'
```
