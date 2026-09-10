# Phase 17 — Editorial Intelligence Design

**Status:** design only (Phase 17.0) — no implementation in this phase  
**Last updated:** 2026-06-28  
**Scope:** Editorial quality layer — stronger WIM, ranking, narrative, cross-topic synthesis, quality audit  
**Prerequisite:** Phases 7–16 (ingestion, assembly, WIM batch, narrative, voice, pipeline ~72s)

Related: [phase14-voice-narrative-design.md](./phase14-voice-narrative-design.md), [phase16-implementation.md](./phase16-implementation.md)

---

## Executive Summary

WhatsNews already delivers a fast, reliable daily pipeline. The next leap is **editorial differentiation**: content that reads like a professional intelligence briefing, not automated headline aggregation.

Phase 17 introduces an **Editorial Intelligence layer** — a set of explainable rules, structured AI prompts, and quality gates that sit on top of existing ingestion, assembly, WIM, and narrative modules. No new infrastructure. No agents, queues, vector DB, or personalization.

```
RSS ingest → assembly → Editorial Intelligence → WIM → narrative → voice
                              ↑
                    ranking, synthesis, audit
```

---

## 1. Product Goals

### Primary goals

| Goal | Description | Success signal |
|------|-------------|----------------|
| **Answer the four briefing questions** | What happened? Why does it matter? What to watch? How are stories connected? | Qualitative editorial review; user feedback |
| **Reduce generic phrasing** | Eliminate template-feel WIM and disconnected narrative sections | Audit: generic-phrase rate ↓ |
| **Explainable editorial choices** | Every top story and WIM can trace to source + scoring reason | Admin audit shows score breakdown |
| **Preserve trust** | No facts beyond source articles; no fake certainty | Grounding checks pass |
| **Stay fast** | Full pipeline remains under ~90s target | `timing_seconds.total` unchanged ±10% |

### Non-goals (Phase 17)

- New mobile UI or reader features
- User accounts, personalization, recommendation engine
- Vector search, RAG over historical corpus
- Autonomous agents or multi-step reasoning loops
- Real-time breaking news or push-by-story triggers
- Cross-day trend analysis (“this is the third week in a row…”)

### Product gate

Every Phase 17 change must pass:

> Does this make the briefing feel like an **editor wrote it for an informed generalist**, not like five RSS summaries with filler?

---

## 2. Editorial Principles

1. **Signal over volume** — Fewer, sharper stories beat filling five slots with weak items.
2. **Consequence over description** — WIM explains *so what*, not *what the headline already said*.
3. **Grounded synthesis only** — Connections and watch items must cite today’s selected articles.
4. **Explicit uncertainty** — Use “may,” “could,” “watch for” when sources do not confirm outcomes.
5. **Topic integrity** — Each topic report stands alone; cross-topic links are additive, not confusing.
6. **Source diversity** — No briefing dominated by one outlet unless the day truly warrants it.
7. **Explainable ranking** — Scores are keyword/rule-based and auditable, not opaque ML.
8. **Editorial voice consistency** — Analyst tone: concise, neutral, implication-forward; no hype words (`important`, `significant`, `game-changer`).
9. **Fail soft** — Quality warnings surface in admin; pipeline still completes with rule-based fallbacks.
10. **Incremental delivery** — Ship ranking + WIM framework before cross-topic synthesis.

---

## 3. Content Quality Problems Today

Based on the current codebase (`assembly.py`, `wim/generator.py`, `narrative/generator.py`, `/admin/briefing-quality-audit`):

| Problem | Where it shows up | Example |
|---------|---------------------|---------|
| **Template WIM** | Rule-based drafts use category templates; AI polish can retain generic structure | “A development in {topic} that looks incremental on the surface…” |
| **Weak impact specificity** | WIM lacks structured impact type (policy, market, etc.) | “This matters because it shows continued momentum.” |
| **Headline-list narrative** | Key developments section enumerates topics with similar transitions | “On Technology: … On Markets: …” |
| **Shallow watch-next** | `_extract_watch_lines` uses keyword grep (`summit`, `vote`) | “Watch for signals around upcoming: [summary snippet]” |
| **No cross-topic threads** | Narrative `_thread_hint` names topics but does not link stories | “threads in AI, Markets, and Geopolitics” |
| **Ranking underused** | `compute_importance_score` is 0–3 keyword tiers; assembly sorts mainly by recency + diversity | Top story may not be highest-impact item |
| **Thin audit** | `/admin/briefing-quality-audit` checks relevance only | No WIM quality, duplication, or narrative coherence |
| **Duplicate phrasing** | Same WIM template hash across articles in one report | Repeated implication sentences |
| **Relaxed assembly fallback** | When strict pool is thin, relaxed candidates fill slots | Off-topic or lower-signal articles |
| **Stale story risk** | 4-day freshness window; no explicit staleness flag in audit | Old feed item ranks if newer pool is empty |

These are editorial gaps, not pipeline reliability gaps. Ingestion and performance (Phase 15–16) are largely solved.

---

## 4. Improved Why It Matters Framework

### 4.1 Target structure

Each WIM becomes a **structured editorial insight** with two sentences minimum, three maximum:

```
[Signal]  — What changed, grounded in title/summary (1 sentence)
[Impact]  — Typed consequence with second-order effect (1–2 sentences)
```

### 4.2 Impact types (at least one required)

| Type | Code | When to use |
|------|------|-------------|
| Business impact | `business` | Earnings, M&A, corporate strategy, labor |
| Policy impact | `policy` | Regulation, legislation, enforcement |
| Market impact | `market` | Prices, rates, equities, commodities |
| Technology impact | `technology` | Product shifts, infrastructure, standards |
| Geopolitical impact | `geopolitical` | Conflict, diplomacy, sanctions, alliances |
| Consumer impact | `consumer` | Prices, privacy, safety, access |
| Second-order | `second_order` | Downstream effects on adjacent sectors |

### 4.3 Banned patterns (quality gate)

- “continued momentum”, “worth watching”, “important development”, “significant shift” without specifics
- Restating the headline with different words
- Invented numbers, dates, or actors not in title/summary
- Words: `important`, `significant`, `crucial` (already in AI prompt; enforce in gate)

### 4.4 Generation pipeline (evolution of Phase 16.1)

```
article + topic
    ↓
rule-based draft (category template)     ← keep for determinism / offline
    ↓
structured AI batch (JSON)               ← extend Phase 16.1 payload
    ↓
WIM quality gate                         ← new
    ↓
persist why_it_matters + impact_type     ← optional column or JSON metadata
```

**Proposed batch JSON shape:**

```json
{
  "articles": [
    {
      "title": "exact title",
      "why_it_matters": "…",
      "impact_type": "market",
      "impact_entities": ["Fed", "rate cuts"]
    }
  ]
}
```

`impact_entities` must appear in title or summary (grounding check).

### 4.5 Fallback behavior

- AI batch failure → per-article fallback (unchanged)
- Quality gate failure → keep rule-based draft + log warning (do not block pipeline)
- Optional admin regen for failed items only

---

## 5. Improved Daily Narrative Framework

### 5.1 Editorial arc (keep six sections, enrich content)

| Section | Current | Phase 17 target |
|---------|---------|-----------------|
| `opening` | Topic count + thread hint | **Lead paragraph**: day’s dominant theme in one sentence; name top story topic |
| `top_story` | Title + source + WIM snippet | **Editorial lead**: why *this* story leads; tie to impact type |
| `key_developments` | Per-topic bullets | **Thematic clusters** within section; transitions between clusters |
| `why_it_matters` | Concatenated WIM quotes | **Synthesized implications** — 2–3 themes, not N quotes |
| `what_to_watch_next` | Keyword grep + generic monitors | **Concrete watch items** from article text + calendar cues |
| `closing` | Product CTA | Short sign-off; optional one-line “big picture” |

### 5.2 Narrative generation modes

1. **Rule-based skeleton** (current `generator.py`) — always runs first
2. **Structured AI polish** (extend `narrative/refine.py`) — one request per daily script with section JSON
3. **Quality gate** (extend `narrative/quality.py`) — coherence + grounding checks

AI polish input: ranked articles + WIM + cross-topic threads (Section 7). Output: same six section IDs, enriched text.

### 5.3 Voice constraints (unchanged)

- No URLs in spoken text
- 300–1800 words; target 500+
- Minimum 3 unique article refs
- No hallucinated facts

---

## 6. Story Selection Principles

Assembly already implements relevance, quality exclusions, source diversity (`MAX_PER_SOURCE=2`), and freshness (`FRESHNESS_WINDOW_DAYS=4`). Phase 17 **extends selection scoring**, not the overall architecture.

### 6.1 Selection score (per candidate article)

Explainable weighted sum (integer 0–100):

| Factor | Weight | Source |
|--------|--------|--------|
| Importance tier | 0–30 | Extend `compute_importance_score` (currently 0–3) |
| Recency | 0–20 | Hours since `published_at` |
| Source credibility | 0–15 | Static tier map per `news_sources.name` |
| Topic relevance strictness | 0–15 | Strict keyword match = 15; relaxed = 5 |
| Novelty | 0–10 | Title hash not seen in last N days for topic |
| Diversity bonus | 0–10 | Underrepresented source in current selection |

### 6.2 Selection algorithm (unchanged shape)

1. Filter: quality + topic quality + freshness
2. Split: strict vs relaxed relevance pools (existing)
3. Sort candidates by selection score (not just recency)
4. Greedy pick with `MAX_PER_SOURCE` and `MAX_ARTICLES_PER_REPORT=5`
5. Prefer strict pool; backfill from relaxed only if under minimum (e.g. 3)

### 6.3 Under-fill policy

- Minimum 3 articles per topic report (warning if below)
- Empty strict pool → admin warning + relaxed backfill (existing behavior, surfaced in audit)

---

## 7. Cross-Topic Synthesis

Start simple: **keyword bridge table**, not ML clustering.

### 7.1 Bridge definitions (curated, editable)

```python
CROSS_TOPIC_BRIDGES = [
    {
        "id": "ai_chips_markets",
        "topics": ["Artificial Intelligence", "Technology", "Markets"],
        "keywords": ["nvidia", "semiconductor", "chip", "export controls", "data center"],
        "label": "AI infrastructure and chip supply",
    },
    {
        "id": "energy_geopolitics",
        "topics": ["Energy", "Geopolitics"],
        "keywords": ["opec", "sanctions", "pipeline", "lng", "strait"],
        "label": "Energy security and geopolitical risk",
    },
    # … healthcare+regulation, defense+technology, climate+markets
]
```

### 7.2 Detection algorithm

For each bridge, count today’s selected articles (across topics) matching ≥1 keyword. If ≥2 topics represented with ≥1 article each → **active thread**.

### 7.3 Usage

- **Narrative opening / synthesis section**: one sentence per active thread, citing topics only (no new facts)
- **Admin audit**: list active threads for the day
- **Optional mobile later**: not Phase 17 UI scope

### 7.4 Example output

> “Two threads run through today’s briefing: AI infrastructure shows up in Technology and Markets coverage around chip export rules, while Energy and Geopolitics both touch LNG supply routes in the eastern Mediterranean.”

---

## 8. What-to-Watch-Next Generation

### 8.1 Current limitation

`_extract_watch_lines` greps fixed keywords in title/summary/WIM. Often produces generic lines.

### 8.2 Improved approach

**Per-article watch extraction** (rule + optional AI):

| Signal type | Detection | Output template |
|-------------|-----------|-----------------|
| Scheduled event | regex: dates, “hearing”, “vote”, “earnings”, “summit” | “Watch [date/event] for …” |
| Policy pending | “proposed”, “draft rule”, “comment period” | “Monitor whether [agency] finalizes …” |
| Market catalyst | “Fed”, “CPI”, “jobs report”, “OPEC meeting” | “Markets will watch …” |
| Escalation risk | “sanctions”, “military”, “strike” | “Watch for response from …” (entities from article only) |

**Daily aggregation** (narrative `what_to_watch_next`):

1. Collect top 1 watch item per topic from selected articles
2. Deduplicate by normalized entity
3. Cap at 4 items + 1 cross-topic watch if bridge active
4. Quality gate: each item must reference a source article title in `article_refs`

### 8.3 Optional structured field

Store on article row or sidecar JSON:

```json
{ "watch_item": "Fed decision Wednesday", "watch_horizon": "this_week" }
```

Generated during WIM batch (same API call) to avoid extra latency.

---

## 9. Editorial Ranking / Top Story Logic

### 9.1 Global top story (narrative + push)

Current: first article after `compute_importance_score` sort in `narrative/loader.py`.

**Phase 17 global rank score** (across all topics, max ~50 articles):

```
global_score =
    selection_score * 2
  + cross_topic_bonus (15 if article participates in active bridge)
  + recency_bonus
  + source_credibility
```

Pick highest `global_score` article as:

- Narrative `top_story` lead
- Push notification dynamic copy (existing `_build_push_copy`)

### 9.2 Per-topic lead

Highest selection score within each topic report (may differ from global top).

### 9.3 Explainability

Persist or compute on read:

```json
{
  "article_id": 123,
  "selection_score": 78,
  "breakdown": {
    "importance": 24,
    "recency": 18,
    "source": 12,
    "relevance": 15,
    "novelty": 9
  },
  "is_global_top_story": true
}
```

Admin endpoint exposes breakdown for editorial review.

---

## 10. Quality Scoring

### 10.1 Layers

| Layer | When | Blocks publish? |
|-------|------|-----------------|
| Assembly gate | Selection | No — warnings only |
| WIM gate | After WIM generation | No — fallback to rule draft |
| Narrative gate | After script generation | Yes — status `failed` (existing) |
| Daily editorial audit | Post-pipeline | No — admin report |

### 10.2 WIM quality checks

- Minimum length (40 chars), maximum (500)
- Contains impact type indicator (keyword list per type or structured field)
- No banned generic phrases
- No headline duplication (>70% token overlap with title)
- Grounding: ≥1 significant token from title or summary in WIM body

**Score:** 0–100; flag if < 60.

### 10.3 Narrative coherence checks (extend `quality.py`)

- Section transitions: no consecutive sections starting with same phrase
- Duplicate sentence detection across sections
- `what_to_watch_next` has ≥2 concrete watch items (not generic filler)
- Cross-topic thread mention if ≥2 active bridges (warning if missing)

### 10.4 Daily briefing audit score

Per topic + global:

| Check | Weight |
|-------|--------|
| Article count ≥ 3 | 20 |
| All WIM present | 20 |
| Avg WIM quality ≥ 70 | 20 |
| Source diversity (≥2 sources) | 15 |
| No stale articles (>48h) | 15 |
| Strict relevance ≥ 80% of slots | 10 |

**Overall editorial score** 0–100 in admin dashboard.

---

## 11. Backend Architecture

### 11.1 New package: `app/editorial/`

Keep modules small and testable. No new services.

```
app/editorial/
  __init__.py
  ranking.py          # selection_score, global_top_story, source credibility map
  wim_framework.py    # impact types, banned phrases, WIM quality gate
  wim_prompt.py       # batch prompt builders (extends wim/batch.py)
  synthesis.py        # cross-topic bridge detection
  watch.py            # watch-item extraction
  narrative_prompt.py # structured narrative polish prompts
  audit.py            # daily editorial audit aggregator
  models.py           # dataclasses / typed dicts for scores
```

### 11.2 Integration points (existing modules)

| Module | Change |
|--------|--------|
| `assembly.py` | Sort/select by `selection_score`; emit score breakdown in logs |
| `wim/batch.py` | Extended JSON schema; call `wim_framework.quality_gate` |
| `wim/service.py` | Pass through impact metadata |
| `narrative/loader.py` | Use `global_top_story()` for ordering |
| `narrative/generator.py` | Inject cross-topic threads + watch items |
| `narrative/refine.py` | Structured section polish |
| `narrative/quality.py` | Coherence + watch checks |
| `main.py` | `/admin/editorial-audit`; pipeline stats `editorial` block |

### 11.3 AI usage pattern (unchanged infrastructure)

- Reuse `app/ai/registry` + batch patterns from Phase 16.1
- WIM: 1 batch call per topic (extend prompt)
- Narrative: 1 optional polish call per daily script
- No new external services

### 11.4 Performance budget

| Stage | Current | Phase 17 delta |
|-------|---------|----------------|
| Assembly | ~32s | +1–2s (scoring in Python) |
| WIM | ~10s warm | +0–3s (richer prompt, same batch count) |
| Narrative | ~3s | +2–5s (optional polish) |
| **Total** | ~72s | Target **< 85s** |

---

## 12. API / Data Model Changes

### 12.1 Schema changes (minimal)

**Option A — JSON metadata columns (recommended for MVP):**

```sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS editorial_metadata JSONB;
-- { "impact_type", "selection_score", "watch_item", "wim_quality_score" }

ALTER TABLE daily_reports ADD COLUMN IF NOT EXISTS editorial_audit JSONB;
-- snapshot of daily audit scores after pipeline
```

**Option B — normalized tables (defer unless needed):**

- `editorial_scores (article_id, score, breakdown, computed_at)`
- `cross_topic_threads (report_date, bridge_id, topic_ids[])`

Start with Option A to avoid migration sprawl.

### 12.2 New admin endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /admin/editorial-audit?date=` | Full editorial quality report |
| `GET /admin/editorial-audit/top-story?date=` | Global top story + score breakdown |
| `GET /admin/editorial-audit/threads?date=` | Active cross-topic bridges |
| `POST /admin/editorial/regenerate-wim?topic=` | Re-run WIM for one topic (existing pattern) |

Extend existing `/admin/briefing-quality-audit` or supersede with richer `/admin/editorial-audit`.

### 12.3 Public API

**No mobile API changes required for Phase 17.** Existing `/daily-report`, `/history`, `/narratives/latest` benefit from better content automatically.

Optional later: expose `impact_type` on article items in daily report JSON.

### 12.4 Source credibility map

```python
# app/editorial/ranking.py — config, not ML
SOURCE_CREDIBILITY_TIER = {
    "BBC World": 3,
    "Reuters": 3,
    "FT Markets": 3,
    # …
    "default": 1,
}
```

Editable via env JSON or DB table in a later phase.

---

## 13. Pipeline Integration

### 13.1 Updated pipeline flow

```
ingest
  ↓
assembly (+ selection_score on assign)
  ↓
cross-topic thread detection (read assigned articles)
  ↓
WIM batch (+ impact_type, watch_item, quality gate)
  ↓
narrative generate (+ threads, global top story)
  ↓
narrative refine (optional AI polish)
  ↓
narrative quality gate
  ↓
editorial audit snapshot → daily_reports.editorial_audit
  ↓
voice (unchanged)
```

### 13.2 Pipeline response extension

Add to `POST /admin/run-pipeline` stats:

```json
{
  "editorial": {
    "global_top_story": { "topic": "Technology", "title": "…", "score": 82 },
    "active_threads": ["ai_chips_markets"],
    "avg_wim_quality_score": 74,
    "topics_below_threshold": [],
    "overall_editorial_score": 81
  }
}
```

### 13.3 Failure behavior

- Editorial audit failure → log warning; pipeline `status: partial` only if narrative fails
- WIM quality failures → count in `generation.wim_quality_warnings`
- Never block ingest or assembly on editorial scores

---

## 14. Observability / Audit

### 14.1 Structured logs

| Event | Fields |
|-------|--------|
| `editorial_selection_scored` | topic, article_id, selection_score, breakdown |
| `editorial_global_top_story` | article_id, topic, global_score |
| `editorial_thread_active` | bridge_id, topics, article_count |
| `editorial_wim_quality` | topic, article_id, score, passed, reasons |
| `editorial_audit_complete` | date, overall_score, topic_scores |

### 14.2 Admin console (existing Operator Console)

Surface in admin UI later; Phase 17 backend-only:

- Daily editorial score card
- Per-topic WIM quality table
- Top story explanation
- Active cross-topic threads
- Links to regenerate WIM / narrative

### 14.3 AI health dashboard integration

Extend `app/ai/dashboard.py` session stats:

- `wim_quality_fail_count`
- `narrative_coherence_warnings`
- Token usage unchanged (same call counts)

### 14.4 Retention

- `daily_reports.editorial_audit` JSON snapshot per run
- Generation runs table unchanged; optional `editorial_score` column later

---

## 15. Implementation Plan

Phased delivery within Phase 17.x. Each sub-phase is independently shippable.

| Phase | Scope | Est. effort | Depends on |
|-------|-------|-------------|------------|
| **17.1** | `editorial/ranking.py`; assembly uses `selection_score`; logging + admin score breakdown | 3–4 days | — |
| **17.2** | WIM framework: impact types, banned phrases, extended batch JSON, WIM quality gate | 4–5 days | 17.1 |
| **17.3** | Global top story + push copy uses global rank; `editorial_metadata` on articles | 2–3 days | 17.1 |
| **17.4** | Cross-topic bridges + `synthesis.py`; narrative opening uses threads | 3–4 days | 17.1 |
| **17.5** | Watch-next extraction; narrative `what_to_watch_next` rewrite | 3 days | 17.2 |
| **17.6** | Narrative coherence quality gate + optional structured polish | 4–5 days | 17.4, 17.5 |
| **17.7** | `/admin/editorial-audit` + pipeline `editorial` stats block | 3 days | 17.2–17.6 |
| **17.8** | Source credibility map + novelty scoring | 2 days | 17.1 |

**Recommended first ship:** 17.1 + 17.2 (ranking + WIM framework) — highest user-visible quality gain.

### 17.x verification checklist

```bash
# Pipeline completes with editorial stats
curl -X POST http://localhost:8000/admin/run-pipeline \
  -H "X-Admin-Key: whatsnews-dev-key" \
  | jq '{timing_seconds, editorial, generation}'

# Editorial audit
curl -s http://localhost:8000/admin/editorial-audit \
  -H "X-Admin-Key: whatsnews-dev-key" | jq .

# WIM spot check
curl -s "http://localhost:8000/daily-report?topic=Technology" \
  | jq '.articles[] | {title, why_it_matters}'
```

### Rollback strategy

Each sub-phase is feature-flagged via env:

```
ENABLE_EDITORIAL_RANKING=true
ENABLE_WIM_IMPACT_FRAMEWORK=true
ENABLE_CROSS_TOPIC_SYNTHESIS=true
ENABLE_NARRATIVE_EDITORIAL_POLISH=true
```

Defaults `false` until verified; rule-based paths remain when disabled.

---

## Appendix A — Example WIM (before / after)

**Before (generic template):**

> A development in Technology that looks incremental on the surface. The structural significance becomes clear when you follow who's responding and how fast.

**After (Phase 17 target):**

> Apple expanded on-device AI features across its core OS releases, pushing more inference to local hardware. **Technology impact:** This shifts competitive pressure toward chip efficiency and privacy-preserving models, which may accelerate edge-AI adoption by enterprise buyers evaluating data residency rules.

---

## Appendix B — Example narrative opening (Phase 17 target)

> Good morning. Today’s briefing is shaped by two forces: chip export policy rippling through Technology and Markets, and renewed energy supply concerns linking Energy and Geopolitics. The lead story comes from Technology, where [headline essence]. We will walk through the key developments, why they matter, and what to watch next.

---

## Appendix C — Relationship to existing docs

| Doc | Relationship |
|-----|--------------|
| `phase14-voice-narrative-design.md` | Phase 17 extends narrative *content* quality; does not change six-section contract |
| `phase16-implementation.md` | WIM batch infrastructure reused; prompt/schema extended |
| `phase15-implementation.md` | Ingestion performance preserved; no changes required |

---

**End of Phase 17.0 design document.**
