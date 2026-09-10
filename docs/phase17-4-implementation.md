# Phase 17.4 — Perspective-powered Narrative

**Status:** implemented  
**Prerequisite:** Phase 17.3 editorial perspective, Phase 14 narrative

## Summary

Daily narrative generation now consumes a **ready editorial perspective** when available. The perspective becomes the organizing thesis: opening introduces the headline, top_story develops the perspective, key_developments cites supporting evidence, and what_to_watch_next uses perspective watch items.

If no ready perspective exists, narrative falls back to the prior rule-based behavior without failing.

## Section mapping (same six canonical IDs)

| Section | Perspective-aware content |
|---------|---------------------------|
| `opening` | Day intro + editorial headline / thesis |
| `top_story` | Perspective body + lead supporting story |
| `key_developments` | Supporting evidence articles, then other topics |
| `why_it_matters` | Theme synthesis + supporting WIM snippets |
| `what_to_watch_next` | `perspective.watch_next` bullets |
| `closing` | Brief synthesis referencing headline |

## Metadata (`script_json.metadata`)

```json
{
  "perspective_used": true,
  "perspective_id": 1,
  "supporting_evidence_used_count": 5,
  "perspective_theme_count": 4,
  "fallback_reason": null,
  "perspective_headline": "...",
  "perspective_confidence": "high"
}
```

When perspective is not used, `perspective_used: false` and `fallback_reason` explains why (`no_ready_perspective`, `perspective_not_ready`, `perspective_incomplete`).

## Files changed

- `app/narrative/generator.py` — perspective-aware builders + fallback
- `app/narrative/service.py` — loads perspective, passes to generator, returns metadata
- `app/narrative/models.py` — `metadata` on `NarrativeScript`
- `app/narrative/loader.py` — `article_id` on `RankedArticle`
- `app/narrative/repository.py` — exposes `metadata` in API dict
- `app/briefing_repository.py` — `id` on article items (internal loader use)

## Generation method

- With perspective: `rule_v1+perspective`
- Fallback: `rule_v1`

## Next

- Phase 17.5 — Watch Next daily aggregation refinements
- Mobile UI can later surface perspective + narrative together
