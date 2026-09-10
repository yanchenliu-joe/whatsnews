# Phase 17.2 — Editorial Why It Matters

**Status:** implemented  
**Prerequisite:** Phase 17.1 editorial metadata, Phase 16.1 batch WIM

## Summary

WIM generation now consumes Phase 17.1 editorial metadata to produce impact-aware, less generic paragraphs. Structured batch JSON, a quality gate, and an improved rule-based fallback protect grounding without blocking the pipeline.

## Flow

```
editorial_metadata (17.1)
    ↓
impact-aware rule draft (editorial_wim.py)
    ↓
batch AI refinement (extended prompt + JSON)
    ↓
quality gate (quality.py)
    ↓ pass → persist why_it_matters + editorial_metadata.wim
    ↓ fail → rule fallback + quality_flags
```

## Batch JSON schema

```json
{
  "articles": [
    {
      "title": "...",
      "why_it_matters": "...",
      "impact_type_used": ["market", "technology"],
      "watch_next": "...",
      "confidence": "high"
    }
  ]
}
```

## Stored metadata

`articles.editorial_metadata.wim`:

```json
{
  "impact_type_used": ["technology"],
  "watch_next": "Watch whether...",
  "confidence": "high",
  "source": "ai",
  "quality_flags": []
}
```

## Quality gate checks

- Minimum length (80 chars), maximum (550)
- Banned generic phrases (`continued momentum`, `could have implications`, etc.)
- Banned words: `important`, `significant`, `crucial`
- Grounding in title/summary tokens
- Concrete actor (tags, proper nouns, or source)
- Forward-looking watch signal

Failures fall back to `generate_editorial_why_it_matters()` — pipeline continues.

## Pipeline metrics (`generation`)

| Field | Meaning |
|-------|---------|
| `wim_quality_pass_count` | AI/cache outputs passing gate |
| `wim_quality_fallback_count` | Rule fallback after gate or AI failure |
| `generic_phrase_block_count` | Fallbacks triggered by banned phrases |
| `impact_type_distribution` | Counts by impact type used |

## Cache

Refinement cache bumped to `wim_v2` key — old generic cached WIM is not reused.

## New / changed files

- `app/wim/quality.py` — quality gate
- `app/wim/editorial_wim.py` — impact-aware rule WIM
- `app/wim/batch.py` — extended prompt, structured parse, gate integration
- `app/wim/service.py` — metadata load/persist, metrics
- `app/wim/metrics.py` — new generation metrics
- `app/wim/cache.py` — v2 cache key

## Next

- **17.3** — Editorial Perspective
- **17.4** — Cross-topic Insight
- **17.5** — Watch Next (daily aggregation)
