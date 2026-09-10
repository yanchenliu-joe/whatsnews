# Phase 17.5 — Watch Next Aggregation

**Status:** implemented  
**Prerequisite:** Phase 17.1–17.3 (editorial metadata, WIM, perspective)

## Summary

Adds a unified **Watch Next** layer that aggregates forward-looking signals from WIM `watch_next`, editorial perspective watch items, cross-topic bridges, and high-importance article themes. Rule-based only — no AI.

## Pipeline flow

```
WIM → Perspective → Watch Next → Narrative → Voice
```

Narrative continues using perspective watch items (Phase 17.6 can wire aggregated Watch Next).

## Output shape

```json
{
  "report_date": "2026-06-28",
  "status": "ready",
  "items": [
    {
      "text": "Monitor whether energy security and geopolitical risk shows up across Geopolitics, Energy coverage this week.",
      "reason": "Cross-topic thread detected in 4 articles across 2 topics.",
      "topics": ["Energy", "Geopolitics"],
      "impact_types": ["energy", "geopolitics"],
      "supporting_article_ids": [123, 456],
      "confidence": "high"
    }
  ],
  "generated_at": "..."
}
```

## Ranking

Candidates scored by:

- Max `importance_score` of supporting articles
- Topic count (+12 each)
- Impact type diversity (+5 each)
- Perspective source (+20)
- Cross-topic with 2+ topics (+15)

Top 3–6 items retained after merge/dedup.

## API

| Endpoint | Auth |
|----------|------|
| `GET /watch-next/latest` | Public |
| `GET /watch-next/daily/{date}` | Public |
| `POST /admin/watch-next/generate?date=&regenerate=` | Admin key |

## Pipeline metrics (`watch_next`)

- `watch_next_status`
- `watch_next_item_count`
- `watch_next_confidence_distribution`
- `watch_next_generation_seconds`

## Migration

`backend/migrations/0013_phase_17_5_editorial_watch_next.sql`

## Next

- **17.6** — Narrative consumes aggregated Watch Next
