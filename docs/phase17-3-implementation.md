# Phase 17.3 — Editorial Perspective

**Status:** implemented  
**Prerequisite:** Phase 17.1 editorial metadata, Phase 17.2 WIM

## Summary

Adds a daily **Editorial Perspective** — the product’s editorial judgment about what today’s news means (not a summary). Generated after WIM, before narrative. Narrative does not consume it yet (Phase 17.4).

## Pipeline flow

```
Assembly → Editorial Engine → WIM → Editorial Perspective → Narrative → Voice
```

## Storage

Table `editorial_perspectives` (migration `0010_phase_17_3_editorial_perspectives.sql`):

- `perspective_json` — full API payload
- Denormalized: `headline`, `perspective_text`, `confidence`, `themes`, `supporting_article_ids`

## Generation

1. Load publishable articles with `editorial_metadata` + WIM
2. Rank by `importance_score`
3. Rule-based perspective (`rule_v1`): themes, bridges, headline, 120–220 words, 3–5 evidence, 2–4 watch items
4. Optional AI polish when `ENABLE_PERSPECTIVE_AI_REFINE=true` (default off)
5. Quality gate → `status=ready` or `failed`

## API

| Endpoint | Auth | Behavior |
|----------|------|----------|
| `GET /perspectives/latest` | Public | Latest ready perspective; 404 if missing |
| `GET /perspectives/daily/{date}` | Public | Ready perspective for date; 404 if missing |
| `POST /admin/perspectives/generate?date=&regenerate=` | Admin key | Generate/regenerate |

## Pipeline metrics (`editorial_perspective`)

- `perspective_status`
- `perspective_confidence`
- `perspective_theme_count`
- `perspective_supporting_article_count`
- `perspective_generation_seconds`

## Config

| Env | Default | Purpose |
|-----|---------|---------|
| `ENABLE_PERSPECTIVE_AI_REFINE` | `false` | Optional OpenAI polish |

## Migration

```bash
backend/migrations/0010_phase_17_3_editorial_perspectives.sql
```

## Next

- **17.4** — Cross-topic insight; narrative consumes perspective
