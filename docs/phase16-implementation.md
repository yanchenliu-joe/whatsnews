# Phase 16.1 — Batch Why It Matters Generation

**Status:** complete  
**Last updated:** 2026-06-28

## Goal

Reduce Why It Matters (WIM) stage runtime by replacing per-article OpenAI calls with one structured JSON batch request per topic.

## Before

- `_fill_missing_why_it_matters` called `refine_with_ai()` once per article (~N API calls per topic).
- Full pipeline WIM stage ≈ 44s with ~10 topics × ~3 articles each.

## After

- `app/wim/batch.py` — one `wim_batch` OpenAI call per topic with JSON output.
- Per-article cache preserved (`app/wim/cache.py`).
- Batch failure or missing entries fall back to single-article `wim_refine`.
- Rule-based draft text preserved as input (same quality pipeline).

## Metrics (`stats.generation`)

| Field | Meaning |
|-------|---------|
| `wim_requests` | OpenAI calls (batch + single fallbacks) |
| `wim_articles_generated` | Articles that received new WIM text |
| `average_articles_per_request` | `batch_articles / wim_requests` |

## Verification

```bash
curl -X POST http://localhost:8000/admin/run-pipeline \
  -H "X-Admin-Key: whatsnews-dev-key" \
  | jq '{timing_seconds, generation: {wim_requests, wim_articles_generated, average_articles_per_request}}'
```

Expected: `timing_seconds.why_it_matters` < 20s on cold runs with `WIM_TOPIC_CONCURRENCY=5`; `wim_requests` ≈ topic count (not article count).

| Variable | Default | Purpose |
|----------|---------|---------|
| `WIM_TOPIC_CONCURRENCY` | `5` | Parallel topic WIM generation workers |
