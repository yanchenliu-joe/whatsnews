# Phase 17.1 — Editorial Engine Foundation

**Status:** implemented  
**Prerequisite:** Phase 17.0 design, Phases 15–16 pipeline

## Summary

Adds a rule-based **Editorial Engine** between assembly and WIM generation. For each selected article, the engine produces structured `editorial_metadata` and pipeline diagnostics under `editorial_engine`.

No AI, embeddings, or frontend changes.

## Pipeline flow

```
RSS → Assembly → Editorial Engine → WIM → Narrative → Voice
```

## Editorial profile shape

Stored in `articles.editorial_metadata` (JSONB):

```json
{
  "importance_score": 86,
  "impact_types": ["technology", "market"],
  "confidence": "high",
  "cross_topic_candidates": ["AI infrastructure and chip supply"],
  "editorial_tags": ["NVIDIA", "HBM", "Memory"],
  "score_breakdown": {
    "signal_tier": 30,
    "recency": 15,
    "source_credibility": 10,
    "topic_relevance": 10,
    "cross_topic": 10,
    "impact_density": 10
  },
  "topic": "Technology"
}
```

## Importance score (0–100)

See `app/editorial/ranking.py` module docstring. Deterministic weighted sum:

| Component | Max points |
|-----------|------------|
| Signal tier (assembly keyword tier 0–3) | 30 |
| Recency (hours since publish/fetch) | 20 |
| Source credibility | 15 |
| Topic relevance (strict vs relaxed) | 10 |
| Cross-topic bridge keyword match | 10 |
| Impact type density (5 × distinct types, cap 15) | 15 |

## New package

```
app/editorial/
  config.py      — ENABLE_EDITORIAL_ENGINE
  ranking.py     — importance score
  impact.py      — impact type detection
  tags.py        — editorial tag extraction
  bridges.py     — cross-topic candidate labels
  profile.py     — profile assembly + confidence
  persist.py     — JSONB write
  service.py     — run_editorial_engine(), in-memory registry
  metrics.py     — pipeline stats normalization
```

## Migration

```bash
# Run in Supabase SQL editor or psql
backend/migrations/0009_phase_17_1_editorial_metadata.sql
```

## Pipeline response

`POST /admin/run-pipeline` includes:

```json
{
  "editorial_engine": {
    "status": "completed",
    "articles_processed": 42,
    "average_importance": 58.3,
    "impact_distribution": { "technology": 12, "market": 8 },
    "top_editorial_tags": [{ "tag": "AI", "count": 5 }],
    "metadata_persisted": 42
  },
  "timing_seconds": {
    "editorial": 0.12
  }
}
```

## Config

| Env | Default | Purpose |
|-----|---------|---------|
| `ENABLE_EDITORIAL_ENGINE` | `true` | Set `false` to skip stage |

## Next phases

- **17.2** — WIM impact framework (consume `impact_types` in batch prompts)
- **17.3** — Editorial Perspective
- **17.4** — Cross-topic Insight (narrative threads)
- **17.5** — Watch Next
