# Phase 14 — Voice Briefing Narrative Design

**Status:** Phase 14.1 implemented — see [phase14-implementation.md](./phase14-implementation.md)  
**Last updated:** 2025-06-26  
**Scope:** Phase 14.0 — Editorial Narrative Script layer only (no TTS, no audio storage)

Related: [phase13-implementation.md](./phase13-implementation.md), [phase13-history-design.md](./phase13-history-design.md)

---

## Executive Summary

Voice Briefings add a new intermediate layer between assembled briefing data and future audio output:

```
Briefing Data (daily_reports + articles)
        ↓
Editorial Narrative Script   ← Phase 14.0–14.1
        ↓
Voice Audio (TTS)            ← Phase 14.2+
```

Phase 14.0 designs the **Editorial Narrative Script** — a structured, listenable morning intelligence script derived from publishable briefings. It is **not** generic TTS of article cards. It is editorial synthesis with a fixed show structure, source grounding, and optional AI polish using the same lightweight pattern as Why It Matters generation.

---

## 1. Product Goals

### Primary goals

| Goal | Description | Success signal |
|------|-------------|----------------|
| **Morning habit** | User can listen to today’s world in 5–10 minutes | Listen completion rate, repeat daily opens |
| **Understanding** | Listener grasps what happened and why it matters | Qualitative review; aligns with written briefings |
| **Editorial coherence** | One narrative, not a headline list | Script reads as a show, not article-by-article |
| **Trust** | Script grounded in source articles | No facts absent from briefing data |
| **Foundation for audio** | Stable script format ready for TTS | Phase 14.2 can attach `audio_url` without redesign |

### Non-goals (Phase 14.0)

- TTS, audio files, playback UI
- Real-time or conversational voice assistant
- Cross-day trend analysis (Phase 15 AI layer)
- Per-user personalized scripts
- Multi-language narration
- Podcast distribution (RSS, Spotify)

### Product positioning gate

Every narrative feature must pass:

> Does this help the user **understand today’s world** in a listenable morning format — not merely hear headlines?

---

## 2. User Experience

### Primary listener journey (Phase 14.3+ mobile; designed now)

1. User opens WhatsNews in the morning (or receives push).
2. **Today’s briefing** screen offers **Listen to morning briefing** (future).
3. App fetches narrative script for today (cross-topic morning show).
4. User hears ~5–10 minutes: opening → top story → developments → why it matters → watch next → close.
5. Optional: tap **Read full briefing** to return to article cards for a topic.

### Script vs read experience

| Dimension | Read (Phase 12–13) | Listen (Phase 14+) |
|-----------|----------------------|---------------------|
| Unit | Per-topic article cards | Cross-topic morning narrative |
| Depth | Full articles + WIM per story | Synthesized themes across stories |
| Duration | User-paced | Target 5–10 minutes |
| Navigation | Topic chips, history, search | Play / pause / scrub (later) |

### Historical voice (deferred)

- Phase 14.1 focuses on **today’s** morning script.
- Historical narrative reuses same generator + `report_date` input (Phase 14.4).
- Aligns with Phase 13 history: one script per date once generated.

### UX principles for script content

- **Spoken language:** short sentences, natural transitions, no bullet lists in audio text.
- **No URLs or “click here”** in script body.
- **Name topics explicitly** when switching themes (“In technology…”, “On climate…”).
- **One narrator voice** (implicit single host; no character dialogue).

---

## 3. Narrative Structure

### Show template (required sections)

The morning narrative is **one script** with six editorial beats:

| # | Section | Purpose | Typical duration |
|---|---------|---------|----------------|
| 1 | **Opening** | Date, framing, “here’s what matters today” | 30–60 sec |
| 2 | **Top story** | Single most important development across all topics | 90–120 sec |
| 3 | **Key developments** | 2–4 additional stories woven by theme, not article order | 2–4 min |
| 4 | **Why it matters** | Connect developments to stakes, patterns, institutions | 60–90 sec |
| 5 | **What to watch next** | Forward-looking signals from sources (no prediction fiction) | 45–60 sec |
| 6 | **Closing** | Brief recap + sign-off | 20–30 sec |

**Target total:** 5–10 minutes (~750–1,500 spoken words at ~150 wpm).

### Synthesis rules (not article-by-article)

- **Do not** structure as “Story one… Story two… Story three…”
- **Do** group by narrative thread (e.g. regulation, markets, geopolitical shift).
- **Do** reference multiple articles inside one thematic paragraph when they reinforce the same point.
- **Top story** selects one article (or tightly linked pair) by cross-topic importance score.
- **Key developments** covers remaining selected articles with transitions.
- **Why it matters** draws primarily from `why_it_matters` fields, reframed for speech.
- **What to watch next** extracts forward cues from summaries/WIM (“hearings”, “vote”, “earnings”, “summit”) — rule-based extraction first.

### Per-topic vs cross-topic

| Script type | Phase | Scope |
|-------------|-------|-------|
| **Morning brief** (default) | 14.1 | One script per `report_date`; aggregates top stories across active topics |
| **Topic brief** (optional) | 14.4+ | One script per `(topic, report_date)` for deep dives / history |

Phase 14.0 standardizes on **Morning brief** as the product-facing default.

---

## 4. Input Data Model

### Source: `briefing_repository` (Phase 13)

All narrative input comes from **publishable briefings** — same rule as history and export.

```python
# Conceptual input bundle for narrative generation
NarrativeInputBundle:
  report_date: str              # YYYY-MM-DD
  generated_at: str             # when script build started
  topics: list[NarrativeTopicInput]

NarrativeTopicInput:
  topic: str
  topic_id: int
  report_id: int
  article_count: int
  articles: list[NarrativeArticleInput]

NarrativeArticleInput:
  position: int                 # importance rank within topic (1 = highest)
  title: str
  summary: str
  source: str
  url: str | None
  why_it_matters: str
  published_at: str | None
  importance_score: float       # from compute_importance_score (derived, not stored)
```

### Loading strategy

1. Call equivalent of `get_briefings_for_date(cur, report_date)` for target date (default: today).
2. If empty → narrative generation fails with clear error (no script).
3. Flatten articles across topics with `(topic, article)` metadata.
4. Rank globally for top story selection; retain topic labels for transitions.
5. Cap articles considered: **max 8–12 stories** across topics (from ~50 raw max at 10×5) to keep script length bounded.

### Relationship to export

- Same article set as `GET /history/date/{date}` for that date.
- Narrative must not include articles missing `why_it_matters`.

---

## 5. Output Script Format

### `NarrativeScript` (canonical JSON)

Stable contract for API, storage, TTS, and future AI layer.

```json
{
  "script_id": "2026-06-26-morning-v1",
  "script_type": "morning_brief",
  "report_date": "2026-06-26",
  "topic": null,
  "status": "ready",
  "version": 1,
  "generated_at": "2026-06-26T08:15:00+00:00",
  "generator": "rule_v1",
  "ai_refine_status": "success",
  "estimated_duration_seconds": 420,
  "word_count": 1050,
  "plain_text": "Good morning. ...",
  "sections": [
    {
      "id": "opening",
      "title": "Opening",
      "text": "Good morning. This is your WhatsNews morning briefing for Friday, June 26.",
      "estimated_seconds": 45,
      "article_refs": []
    },
    {
      "id": "top_story",
      "title": "Top Story",
      "text": "...",
      "estimated_seconds": 105,
      "article_refs": [
        {
          "topic": "Geopolitics",
          "topic_id": 5,
          "report_id": 112,
          "article_url": "https://...",
          "article_title": "...",
          "source": "..."
        }
      ]
    },
    {
      "id": "key_developments",
      "title": "Key Developments",
      "text": "...",
      "estimated_seconds": 180,
      "article_refs": [...]
    },
    {
      "id": "why_it_matters",
      "title": "Why It Matters",
      "text": "...",
      "estimated_seconds": 75,
      "article_refs": [...]
    },
    {
      "id": "what_to_watch",
      "title": "What to Watch Next",
      "text": "...",
      "estimated_seconds": 50,
      "article_refs": [...]
    },
    {
      "id": "closing",
      "title": "Closing",
      "text": "...",
      "estimated_seconds": 25,
      "article_refs": []
    }
  ],
  "source_report_ids": [106, 107, 108, ...],
  "quality_gate": {
    "passed": true,
    "warnings": []
  },
  "audio": {
    "status": "not_generated",
    "url": null,
    "duration_seconds": null,
    "generated_at": null
  },
  "headline": null,
  "summary": null
}
```

### Field notes

| Field | Purpose |
|-------|---------|
| `script_type` | `morning_brief` \| `topic_brief` (future) |
| `status` | `pending` \| `ready` \| `failed` \| `stale` |
| `version` | Increment on regeneration |
| `plain_text` | Full script for TTS input (sections joined with pauses) |
| `sections[]` | Editorial structure + per-section TTS markers later |
| `article_refs` | Traceability to source articles; no hallucination audit |
| `audio` | Placeholder for Phase 14.2; null until generated |
| `headline` / `summary` | Optional card copy for UI (Phase 14.3) |

### Duration estimation

- Rule: `word_count / 150 * 60` seconds (configurable `WORDS_PER_MINUTE`).
- Per-section: proportional to section word count.
- TTS provider may refine duration later; store both estimates and actual.

---

## 6. Backend Architecture

### Module layout (proposed)

```
backend/app/narrative/
  models.py          # NarrativeScript, NarrativeSection dataclasses
  loader.py          # load_narrative_input_bundle() via briefing_repository
  generator.py       # rule-based script assembly
  refine.py          # optional OpenAI polish (mirror why_it_matters pattern)
  quality.py         # length, grounding, duplicate checks
  repository.py      # DB read/write for persisted scripts
```

### Integration points

| Existing component | Role |
|--------------------|------|
| `briefing_repository` | Load publishable briefings |
| `assembly` + scheduler | After WIM generation, trigger narrative job |
| `main.py` scheduler | Extend pipeline: ingest → assemble → WIM → **narrative** |
| `generation_runs` / logging | Optional `narrative_runs` or extend `meta_json` |

### No new infrastructure

- In-process generation (same as WIM and assembly).
- Single FastAPI app, Supabase PostgreSQL.
- No Celery, no S3 requirement until audio phase.

---

## 7. API Design

### Phase 14.1 minimal surface (public read)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/voice/narrative` | Today’s morning script (`status=ready`) |
| `GET` | `/voice/narrative/{report_date}` | Script for date (history) |

Query params (optional, defer if not needed):

- `?script_type=morning_brief` (default)

Responses: `NarrativeScript` JSON as above.

| Status | Condition |
|--------|-----------|
| 200 | Script `ready` |
| 404 | No publishable briefing or no script for date |
| 503 | Database unavailable |

### Admin / pipeline (Phase 14.1)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/voice/narrative/generate` | Generate for today or `?date=` |
| `POST` | `/admin/voice/narrative/regenerate` | Force new version (`?date=`) |
| `GET` | `/admin/voice/narrative/status` | Latest run stats per date |

Protected by `ADMIN_API_KEY` (existing pattern).

### Deferred endpoints

- `GET /voice/narrative/list` — use `/history/dates` + narrative status flag instead initially.
- Streaming audio — `GET /voice/audio/{report_date}` in Phase 14.2.

### Mobile (Phase 14.3)

- `GET /voice/narrative` only for first ship; history audio uses dated path.

---

## 8. Storage Strategy

### Recommendation: **persist scripts** (not regenerate on every read)

| Approach | Pros | Cons |
|----------|------|------|
| On-demand only | No schema | Slow, costly AI, inconsistent intraday |
| **Persist per date** | Fast read, auditable, TTS reuse | Schema + stale handling |

### Proposed table: `briefing_narratives`

```sql
CREATE TABLE IF NOT EXISTS briefing_narratives (
    id              SERIAL PRIMARY KEY,
    script_type     TEXT NOT NULL DEFAULT 'morning_brief',
    report_date     DATE NOT NULL,
    topic_id        INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'pending',
    generator       TEXT NOT NULL,
    ai_refine_status TEXT,
    script_json     JSONB NOT NULL,
    plain_text      TEXT NOT NULL,
    word_count      INTEGER,
    estimated_duration_seconds INTEGER,
    source_report_ids INTEGER[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (script_type, report_date, topic_id, version)
);
```

- **Morning brief:** `topic_id IS NULL`, one active version per date.
- **Topic brief (future):** `topic_id` set.
- `script_json` holds full `NarrativeScript` (sections, refs, audio placeholder).

### Versioning

- Regeneration increments `version`; API returns **latest `ready`** version by default.
- Old versions retained for audit (no auto-delete in Phase 14).

### Staleness

- If assembly re-runs for **today** and article set changes materially, mark script `stale` or auto-regenerate on next scheduler pass.
- **Rule:** compare `source_report_ids` + article URL hashes; mismatch → `stale`.

### Cost control

- One generation per date per scheduler run (not per API read).
- AI refine optional and single-pass per generation.
- Cap input articles before AI call.

### Consistency with history

- Narrative for `report_date` is immutable once day rolls over (same as article snapshot).
- Historical scripts generated lazily on first request or batch backfill (admin).

---

## 9. Generation Strategy (Phase 14.1 — design only)

### Pipeline overview

```
load_narrative_input_bundle(report_date)
  → select_and_rank_articles(max=10)
  → build_rule_based_script()      # deterministic structure
  → optional refine_narrative_ai() # transitions + flow only
  → run_quality_gate()
  → persist briefing_narratives
```

### Step 1: Rule-based core (required)

Deterministic, no API key required.

| Section | Rule-based source |
|---------|-------------------|
| Opening | Template + `formatDate(report_date)` |
| Top story | Highest global `importance_score`; 2–3 sentences from title + summary |
| Key developments | Remaining articles grouped by topic; transition phrases |
| Why it matters | Synthesize top 3 `why_it_matters` strings (trim, de-duplicate phrases) |
| What to watch | Regex/keyword extract from summaries (“tomorrow”, “vote”, “earnings”, “hearing”) |
| Closing | Fixed template + recap one line |

Templates live in `narrative/templates.py` — same spirit as `generate_why_it_matters` category templates.

### Step 2: Optional OpenAI refinement (mirrors WIM)

Only when `OPENAI_API_KEY` is set.

- **Input:** rule-based script + structured article facts JSON.
- **Task:** improve transitions, spoken flow, remove repetition.
- **Constraints (prompt):** do not add facts; do not cite articles not in input; keep section structure; target word count band.
- **Fallback:** on failure or no key → use rule-based script; `ai_refine_status = no_key | fallback`.

No agents, no multi-step chains, no tool use.

### Step 3: Quality gate

See §11. Fail → `status=failed`, log error; do not expose partial script.

### Scheduler integration

After `run_scheduled_pipeline` generation step:

```text
ingest → assemble → why_it_matters → narrative_generate(today)
```

Push notification copy may later reference top story from narrative (optional).

---

## 10. Quality Rules

### A good morning narrative script is:

| Criterion | Measure |
|-----------|---------|
| **Coherent** | Reads as one show; smooth transitions between sections |
| **Right length** | 750–1,500 words (5–10 min); quality gate warns outside band |
| **Non-repetitive** | No duplicate phrases across sections; dedupe similar WIM lines |
| **Grounded** | Every factual claim traceable to `article_refs` |
| **Meaning-forward** | “Why it matters” section ≥15% of word count |
| **Forward-looking** | “Watch next” cites source cues, not invented forecasts |
| **Listenability** | No markdown, bullets, or parenthetical URLs in `plain_text` |
| **Complete** | All six sections present with non-empty `text` |

### Automatic checks (`narrative/quality.py`)

1. Word count in `[MIN_WORDS, MAX_WORDS]` (e.g. 700–1600).
2. Each section has `text` length ≥ minimum.
3. `top_story` has ≥1 `article_ref`.
4. No section `text` contains `http://` or `https://`.
5. Duplicate sentence detection (simple n-gram overlap threshold).
6. All `article_refs` URLs exist in input bundle.
7. Post-AI: optional diff check — new named entities not in source → warning or reject.

### Human review (operator)

- Admin preview of `plain_text` in Operator Console (Phase 14.3).
- Export script as text/PDF optional later.

---

## 11. Error Handling

| Scenario | Behavior |
|----------|----------|
| No publishable briefing for date | No script; API 404; scheduler logs skip |
| Partial topics only | Generate from available topics; warning in `quality_gate` |
| AI refine timeout/error | Fallback to rule-based; `ai_refine_status=fallback` |
| Quality gate fail | `status=failed`; admin can regenerate |
| Concurrent regenerate | DB unique constraint on version; latest wins on read |
| Read during `pending` | API 404 or `status=pending` with 202 (choose one: **404 until ready** for simplicity) |
| Mock mode (no DB) | No narrative; 404 or static demo script (dev only) |

### Logging

Structured events (match existing `[whatsnews] event=` pattern):

- `narrative_started`, `narrative_success`, `narrative_failed`, `narrative_skipped`, `narrative_ai_fallback`

---

## 12. Future TTS Compatibility

### Script → audio (Phase 14.2)

- TTS consumes `plain_text` or per-section `text` with SSML pause markers inserted between sections.
- `sections[].estimated_seconds` guides progress UI.
- `briefing_narratives.script_json.audio` updated after TTS:

```json
"audio": {
  "status": "ready",
  "url": "https://.../briefings/2026-06-26-morning.mp3",
  "duration_seconds": 415,
  "generated_at": "...",
  "provider": "openai_tts"
}
```

Optional separate table `briefing_audio` keyed by `narrative_id` if file metadata grows.

### Mobile playback (Phase 14.3)

- Play button on Today screen when `audio.status=ready`.
- Fallback: “Script only” mode with section headers if audio missing.

### Section markers for TTS

- Insert `\n\n` or SSML `<break time="800ms"/>` between sections in `plain_text` assembly.
- Store `ssml_text` field later without breaking `plain_text` consumers.

---

## 13. Future AI Intelligence Layer Compatibility

Phase 15 “Ask today’s briefing” can use:

| Asset | Use |
|-------|-----|
| `NarrativeScript.plain_text` | Compressed context for Q&A |
| `sections[].article_refs` | Cite specific articles in answers |
| `report_date` + `source_report_ids` | Load full articles for deep explain |
| `why_it_matters` in sources | Already embedded in narrative |

### Compare today vs yesterday

- Load two `NarrativeScript` rows by date; diff summaries in AI layer (not narrative generator).

### Narrative vs chatbot boundary

- Narrative generator: **batch, scheduled, grounded synthesis**.
- AI layer: **interactive, retrieval over same briefing snapshot**.
- Do not merge into one agent pipeline.

---

## 14. Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| **14.0** | This design doc |
| **14.1** | `briefing_narratives` table, rule-based generator, optional AI refine, admin generate, `GET /voice/narrative` |
| **14.2** | TTS integration, audio storage, `audio` block population |
| **14.3** | Mobile listen UI, play/pause, link to read view |
| **14.4** | Historical narrative + audio by date |
| **14.5** | Per-topic scripts (optional), operator script preview |

### Phase 14.1 file checklist (for handoff)

- `backend/app/narrative/*`
- `backend/app/schema.sql` migration snippet
- `backend/app/history.py` or new `voice.py` routes
- Scheduler hook in `main.py`
- No mobile changes required for 14.1

---

## Appendix A — Example section flow (abbreviated)

**Opening:** “Good morning. This is your WhatsNews briefing for Friday, June 26. Across ten topics, three threads dominated today: AI regulation, climate finance, and semiconductor supply chains.”

**Top story:** (Geopolitics article — highest score) “The most significant development…”

**Key developments:** “In technology, … Turning to markets, … In climate, …”

**Why it matters:** “Together, these moves suggest …”

**What to watch:** “Tomorrow, watch for … hearings … earnings …”

**Closing:** “That’s your morning briefing. Open WhatsNews to read the full stories.”

---

## Appendix B — Verification commands (post-implementation)

```bash
# Generate (admin)
curl -X POST "http://localhost:8000/admin/voice/narrative/generate" \
  -H "X-Admin-Key: $ADMIN_API_KEY"

# Read today
curl -s "http://localhost:8000/voice/narrative" | jq '.report_date, .word_count, .sections | length'

# Read by date
curl -s "http://localhost:8000/voice/narrative/2026-06-26" | jq '.status, .estimated_duration_seconds'
```

---

## Appendix C — Deferred items

| Item | Phase |
|------|-------|
| Full calendar UI for voice history | 14.4 |
| Search in voice / transcripts | 15+ |
| FTS on scripts | Not planned |
| Vector embeddings | Not planned |
| Multi-voice / host personas | Not planned |
| Feishu / podcast export | Post-launch |
