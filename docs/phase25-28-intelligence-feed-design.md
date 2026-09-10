# Phases 25–28 — Signal Intelligence, Briefing, Cognitive & Unified Feed

**Status:** Implemented and shipped (all four phases stable in production)
**Written:** 2026-07-13 — retrospective. These phases shipped without a design
doc (Technical Debt #13); this document reconstructs the architecture and
rationale directly from the working code (`app/intelligence/`,
`app/briefing/`, `app/cognitive/`, `app/feed/`) rather than from memory or
planning notes, since none of the latter exist for this work.
**Prerequisite:** Phases 1–18 (ingestion → assembly → editorial engine → WIM
→ narrative → voice → auth), Phase 19 (20-topic expansion), Phase 24/24.2
(feed reliability tracking + lifecycle state on `news_sources`)

Related: [phase17-editorial-intelligence-design.md](./phase17-editorial-intelligence-design.md)
(the editorial engine these phases read `editorial_metadata` from),
[phase18-auth-redesign.md](./phase18-auth-redesign.md)

---

## Executive Summary

Phases 1–18 built a reliable daily pipeline: ingest RSS, assemble up to 5
articles per topic, generate a rule-based-with-AI-polish "Why It Matters"
per article, and produce a narrative/voice briefing. That pipeline answers
*what happened*. Phases 25–28 answer three further questions **without
touching the pipeline at all**:

1. **Which of today's articles actually matter, and which are noise?**
   (Phase 25 — Intelligence: signal scoring + event clustering)
2. **How do I read this as a story, not five bullet points from five feeds
   covering the same event?** (Phase 26 — Briefing: narrative blocks +
   cross-event thread detection)
3. **What should I *do* with this information — is it urgent, who does it
   affect, what's the confidence?** (Phase 27 — Cognitive: impact/risk/
   confidence framing)
4. **How does the client get the right depth automatically, on every
   device, without asking?** (Phase 28/28B — Feed: mode auto-selection +
   fallback chain + response caching)

The defining architectural decision, made once and held consistently across
all four phases:

> **These are read-time transformation layers, not pipeline stages.**
> Each layer is a pure function of already-assembled data
> (`articles.report_id`-linked rows + `news_sources` reliability columns).
> None of them write to the database. None of them are called from
> `run_scheduled_pipeline()`. Each is invoked fresh on every HTTP request
> to its endpoint (with a 300s response cache at the outermost Feed layer
> only — see §5.5).

This buys three things simultaneously: **zero new migrations** (Phases
25–28 introduced none — see the Database section in `ENGINEERING.md`), **zero
new failure-isolation risk** to the 9-stage pipeline's "a stage fails, the
rest still runs" contract (per the Project Principles' "never sacrifice
reliability for elegance"), and **the ability to reprocess today's articles
differently on every request** — a signal-score threshold or a clustering
rule can change and the very next request reflects it, with no backfill
job, because nothing was ever written down in the first place.

All four layers are **pure rule-based computation** — no OpenAI calls, no
ML models, no external APIs, no feature flag (there is no external
dependency to gate; see "AI always has a deterministic fallback" in the
Project Principles — these layers don't even have an AI *path* to fall
back from).

```
                    ┌─────────────────────────────────────────┐
                    │   9-stage pipeline (Phases 1–18, unchanged)  │
                    │   ingest → assemble → editorial → WIM →      │
                    │   perspective → watch-next → narrative → audio → push │
                    └─────────────────────┬─────────────────────┘
                                          │ writes
                                          ▼
                    articles (report_id-linked) + news_sources (reliability)
                                          │ reads (per HTTP request, no writes)
                                          ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  Phase 25 — INTELLIGENCE   signal_score (0–100) per article  │
        │  app/intelligence/          → cluster same-story articles    │
        │                              into events → suppress noise    │
        │                              tier (score < 40)                │
        └─────────────────────────────┬─────────────────────────────┘
                                       │ events (score ≥ 40 only)
                                       ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  Phase 26 — BRIEFING       event → narrative block:          │
        │  app/briefing/               headline, what_happened,        │
        │                              why_it_matters, what_changed,    │
        │                              watch_next + cross-event threads │
        └─────────────────────────────┬─────────────────────────────┘
                                       │ narrative blocks
                                       ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  Phase 27 — COGNITIVE      narrative block → so_what,        │
        │  app/cognitive/               impact_level, risk_level,       │
        │                              who_is_affected,                │
        │                              action_implication, confidence   │
        └─────────────────────────────┬─────────────────────────────┘
                                       │ cognitive blocks
                                       ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  Phase 28/28B — FEED       unified entry point — auto-picks  │
        │  app/feed/                   mode from X-Client-Type/User-    │
        │                              Agent/topic category, falls      │
        │                              back down the chain              │
        │                              cognitive→briefing→signal→raw   │
        │                              if the chosen mode is empty      │
        └─────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                            GET /feed  (mobile app's actual entry point)
```

### Non-goals (held across all four phases)

- No embeddings, no vector search, no LLM calls anywhere in this stack.
- No new DB tables or columns — everything computes from what Phase 1–19
  already wrote.
- No personalization — output is per-topic, not per-user.
- No real-time/streaming updates — same request-time computation model as
  everything else in this product; a 300s cache is the only staleness
  tolerance introduced (Phase 28 only).
- No change to `/daily-report` (Phase ≤17's endpoint) — it still exists,
  still works, unchanged. These four phases are additive.

---

## 1. Phase 25 — Intelligence (signal scoring + event clustering)

**Module:** `app/intelligence/` (`scoring.py`, `clustering.py`, `service.py`,
`routes.py`)
**Endpoint:** `GET /daily-intelligence?topic=`
**Also called internally by:** Briefing, Cognitive, and Feed (every layer
above this one in the stack starts here)

### 1.1 Problem

Assembly (Phase 2) already filters candidates down to ≤5 articles per
topic per day — but "assembled" isn't the same as "important," and
multiple assembled articles routinely cover the *same* real-world event
from different outlets (a Fed rate decision covered by Reuters, Bloomberg,
and a regional business paper). Phase 25 answers two questions no earlier
phase does: *how important is each article, on a comparable 0–100 scale*,
and *which articles are actually the same story*.

### 1.2 Signal scoring (`scoring.py`)

`compute_signal_score(article, source_reliability_score, now)` returns a
0–100 score built from four independently-capped components:

| Component | Range | Inputs |
|---|---|---|
| `impact_score` | 0–30 | Base from the editorial engine's existing `importance_score` (0–3 → 2/8/14/22 base), plus a keyword boost (±8 net: high-impact keyword hits × 4, medium × 2, capped at +8, minus a flat −3 if background/opinion keywords are present) |
| `novelty_score` | 0–20 | Recency only — a step function on article age (20 at <6h, down to 1 at >72h; unknown `published_at` gets a flat 5) |
| `credibility_score` | 0–20 | Source reliability, read from `news_sources.success_count`/`failure_count` (the same columns Phase 24's feed-lifecycle tracking already maintains) — a step function, not linear, so one flaky recent failure doesn't swing a normally-reliable source's score |
| `urgency_score` | 0–30 | Breaking-news keyword presence combined with age — the only component where *both* recency and keyword content gate the score jointly, not additively |

`signal_score = impact + novelty + credibility + urgency` (max 100), then
banded into `signal_tier`: `high` (≥70), `informational` (40–69), `noise`
(<40).

**Why four independently-capped components instead of one formula**: each
component answers a different question (*is this substantively important*
/ *is it fresh* / *can I trust the source* / *is it breaking right now*)
and capping each separately means no single strong signal (e.g. a very
fresh article) can single-handedly push a low-impact story into the `high`
tier — all four have to be at least reasonably strong together. This
mirrors how the editorial engine (Phase 17) already separates
`importance_score` from `impact_types` rather than one blended number, and
reuses that separation instead of inventing a second, competing scoring
philosophy: `impact_score`'s base directly reads `editorial_metadata.importance_score`,
so intelligence scoring is additive on top of Phase 17, not a rival to it.

**Why source reliability is read from `news_sources`, not a separate table**:
Phase 24 already tracks `success_count`/`failure_count` per source for feed
*health* (auto-disable/auto-recover). Phase 25 reuses those exact same
columns for a different purpose — reader-facing *trust* — via
`_load_source_reliability_map()` in `intelligence/service.py`, computing
`100 * success / (success + failure)` per source (defaulting new/unknown
sources to a neutral 70, not 0 or 100 — an unproven source shouldn't be
penalized as unreliable, nor trusted as much as a proven one). One set of
counters, two consumers — no duplicate tracking.

### 1.3 Event clustering (`clustering.py`)

`cluster_articles(articles)` groups same-story articles from different
sources into a single "event," so a Fed decision covered by 4 outlets
becomes one card with 4 sources, not 4 separate cards.

**Algorithm**: single-pass greedy clustering, not a full pairwise
similarity matrix (O(n) cluster-membership checks per article against
existing cluster leads, not O(n²) against every other article):

1. Sort all articles by `signal_score` descending *before* clustering
   begins. This isn't just for output ordering — it's load-bearing for
   correctness: **the highest-signal article always becomes its cluster's
   lead** (the one whose title/tokens define the cluster and whose
   `why_it_matters`/`summary` becomes the event's `summary`), because
   clusters are built by testing each subsequent (lower-signal) article
   against already-formed cluster leads, never the reverse.
2. For each article, test title-token Jaccard similarity (≥0.35) against
   every existing cluster's lead tokens, **and** a 72-hour publication
   window from the cluster lead's timestamp. Both must hold to join.
3. If no existing cluster matches, the article starts its own new
   (single-member) cluster.
4. Each resulting cluster gets a **size bonus** added to its lead's
   `signal_score` to produce the event's final score: `+0` for 1 article,
   up to `+15` for 5+ articles (`_SIZE_BONUS` table) — multi-source
   confirmation of the same story is itself a signal of importance, not
   just a display convenience.

**Why 0.35 Jaccard on titles, not full-text or embeddings**: title tokens
are short, dense with the actual proper nouns/subject of the story, and
this project already had a working precedent for exactly this technique —
`ingestion/persist.py`'s semantic dedup (Phase 15.2, `_SEMANTIC_DEDUP_THRESHOLD
= 0.82`) and `related/matching.py`'s related-articles scoring (Phase 31)
both use the identical title-Jaccard approach. 0.35 is deliberately much
looser than ingestion's 0.82 dedup threshold — dedup is trying to catch
*byte-similar* titles from the same feed; clustering is trying to catch
*topically-similar* titles from *different* outlets, which will naturally
phrase the same event differently ("Fed Cuts Rates" vs. "Federal Reserve
Lowers Interest Rate Target").

**Why a 72-hour window, not "same day"**: a story can break late one day
and get follow-up coverage into the next 1–2 days; a same-calendar-day
window would arbitrarily split a single event across "yesterday's cluster"
and "today's cluster" right at midnight. 72 hours matches assembly's own
`FRESHNESS_WINDOW_DAYS=4`-adjacent freshness philosophy (see `assembly.py`)
without literally reusing that constant, since clustering is windowing
around a specific event's lead timestamp, not around "now."

### 1.4 Noise suppression

`get_daily_intelligence()` (`service.py`) computes every article's
`signal_score`, clusters them, then **returns only `high` + `informational`
tier events** — noise-tier clusters (score <40, after the cluster's own
size bonus) are entirely excluded from the `events` list, counted only in
`noise_suppressed_count` for observability. Suppression happens once here,
and every downstream layer
(Briefing, Cognitive, Feed) inherits it for free simply by consuming
Intelligence's `events` list rather than re-filtering.

### 1.5 Why this has zero new migrations

`get_daily_intelligence()` reads `articles` (already has every column it
needs: `title`, `published_at`, `editorial_metadata`, `body_text`, etc. —
all present since Phases 9/17/22/25's own column additions) and
`news_sources` (reliability columns already added in Phase 24). No new
table, no new column. This is the pattern every phase after this one
follows too.

---

## 2. Phase 26 — Briefing (narrative framing + cross-event threads)

**Module:** `app/briefing/` (`builder.py`, `templates.py`, `service.py`,
`routes.py`)
**Endpoint:** `GET /daily-briefing?topic=&emerging=`
**Calls internally:** Phase 25's `get_daily_intelligence()`
**Also called internally by:** Cognitive, Feed (briefing mode)

### 2.1 Problem

Phase 25's output is already useful (scored, deduplicated, clustered) but
still shaped like a list of events, not something a person reads. Phase 26
transforms each event into a five-field narrative unit and, separately,
detects when several *different* events are actually chapters of the same
ongoing story ("threads").

### 2.2 Two-tier split, not one flat list

`get_daily_briefing()` splits Phase 25's already-noise-filtered events into
two tiers using the *same* score bands Phase 25 already established, not
new thresholds invented at this layer:

| Tier | Score band | Cap | Purpose |
|---|---|---|---|
| **Primary** (`briefing`) | ≥70 (`high` tier) | 8 items | The actual briefing content |
| **Emerging** (`emerging_signals`) | 40–69 (`informational` tier) | 5 items | An optional appendix (`?emerging=true`) — stories worth a mention but not yet confirmed-important enough for the main briefing |

Within each tier, events are ranked by `(-signal_score, -sources_count,
-published_at)` — signal score first, then multi-source confirmation as a
tiebreaker, then recency as the final tiebreaker. Reusing `sources_count`
(a Phase 25 clustering output) as a *ranking* signal here, not just a
*display* field, is deliberate: two events with an identical signal score
should surface the one more outlets are covering.

### 2.3 Narrative block construction (`builder.py`)

`build_narrative_block(event)` produces five fields per event, each with
its own small rule-based derivation — this is the same "editorial
templates over an LLM" philosophy as Phase 17's WIM generation, applied to
an event (a cluster of articles) instead of a single article:

- **`headline`** — the cluster lead's title, with wire-service prefixes
  (`BREAKING:`, `EXCLUSIVE:`, etc.) stripped and truncated to ≤18 words —
  the raw title alone can carry noise a briefing headline shouldn't.
- **`what_happened`** — up to 3 sentences, one drawn from each of up to 3
  distinct-source top articles in the cluster (deduplicated) — a factual
  synthesis, deliberately sourced from *multiple* articles in the cluster
  when available, not just the lead article's own summary, since the
  whole point of clustering was multi-source confirmation.
- **`why_it_matters`** — reuses the lead article's own `why_it_matters`
  (Phase 17.2's WIM output) when present, falling back to impact-type/
  signal-band templates (`WIM_BY_IMPACT_TYPE`/`WIM_BY_SIGNAL_BAND`) when
  not — Briefing doesn't regenerate significance analysis from scratch,
  it reuses Phase 17's already-computed one.
- **`what_changed`** — regex-pattern detection over the headline/title
  text (acquisition, reversal, escalation, restriction, approval,
  increase, decrease, new_launch — `_TITLE_ONLY_PATTERNS` checked before
  the broader `_FULLTEXT_PATTERNS`, since a title match is more reliable
  signal than a full-text keyword hit) mapped to a template sentence
  (`CHANGE_BY_PATTERN`) describing the delta from prior state.
- **`watch_next`** — forward-looking template, selected by impact type
  first, then by keyword match, with a generic fallback
  (`WATCH_NEXT_FALLBACK`) — the same layered-fallback shape used
  throughout this project's rule-based text generation (editorial WIM
  templates, cognitive action-implication templates below).

### 2.4 Cross-event thread detection

Separate from per-event narrative building: `_build_threads()` looks for
named entities (proper nouns / acronyms, via `extract_entities()`) that
appear across **≥2 different primary-tier events**, and merges any events
sharing an entity into a "thread" (e.g. three separate events all
mentioning "OpenAI" across a day become one thread pointing at all three
headlines). Entity groups that overlap (share at least one event) are
transitively merged into a single thread rather than kept as separate
overlapping entity-threads — a simple union-of-sets pass, not a graph
library.

This only makes sense *after* Phase 25's clustering already merged
same-story duplicates — thread detection is specifically for
*related-but-distinct* events (three different developments in one
ongoing situation), which clustering's 0.35 title-similarity threshold
would never catch on its own (different headlines about the same broader
story rarely share 35% of their title tokens).

### 2.5 Why this is a separate phase/module from Intelligence

Intelligence's job (score + dedupe) and Briefing's job (narrate + connect)
are genuinely different concerns with different failure modes — a bug in
thread detection shouldn't be able to corrupt signal scoring, and Briefing
needed its own tier thresholds (70/40 for primary/emerging) that are a
*product* decision (how much to show), independent of Intelligence's
40/70 *classification* boundary (which happens to share the same numbers
today but is a coincidence of the current tuning, not a structural
coupling — Briefing reads `signal_score` values, not tier labels, when
computing its own tiers).

---

## 3. Phase 27 — Cognitive (impact/risk/confidence framing)

**Module:** `app/cognitive/` (`builder.py`, `scoring.py`, `templates.py`,
`service.py`, `routes.py`)
**Endpoint:** `GET /daily-cognitive?topic=`
**Calls internally:** Phase 26's `get_daily_briefing()`
**Also called internally by:** Feed (cognitive mode — the mode the shipped
mobile app actually uses by default)

### 3.1 Problem

Briefing answers "what happened and why does it matter" in prose. Cognitive
adds the layer a decision-maker actually scans for first: *is this
urgent, who does it affect, and how sure are we?* — five new structured
fields laid directly on top of a narrative block, without changing or
duplicating any of Briefing's own five fields.

### 3.2 The five new fields (`builder.py` + `scoring.py`)

| Field | Derivation |
|---|---|
| `so_what` | Reuses the narrative block's own `why_it_matters` when it "reads like interpretation" (>40 chars, doesn't start with an attribution phrase like "According to"); otherwise falls back to an `impact_level`-keyed template (`SO_WHAT_FALLBACK`) |
| `impact_level` | Pure step function of `signal_score`: `critical` (≥80) / `high` (≥60) / `medium` (≥40) / `low` |
| `risk_level` | Keyword-set match (`HIGH_RISK_KEYWORDS`/`MEDIUM_RISK_KEYWORDS`) across headline + what_happened + why_it_matters — high-risk keywords take priority over medium |
| `who_is_affected` | Named-entity extraction (bigram entities like "federal reserve" checked before unigram) against a curated `ENTITY_MAP` (institutions/companies/countries), plus sector inference from the lead article's `editorial_metadata.impact_types` via `IMPACT_TYPE_TO_SECTOR` — capped at 6, institutions ordered first |
| `action_implication` | impact-type-keyed template (`ACTION_IMPLICATIONS[impact_type][impact_level]`) with a level-only fallback (`ACTION_IMPLICATION_FALLBACK`) when no impact type is present |
| `confidence` | 0–100, computed in `scoring.py`'s `compute_confidence()` — see below |

### 3.3 Confidence scoring — the one genuinely new signal at this layer

`compute_confidence()` is the only field here that isn't a straightforward
lookup/template — it's a small additive model starting from a base of 50:

- **+15 per additional confirming source beyond the first, capped at +45**
  (`sources_count` — inherited from Phase 25's clustering output) — this
  is confidence *that the event is correctly reported/classified*, not
  confidence in the outcome itself; more independent outlets covering the
  same story is direct evidence the clustering and the story are both
  real.
- **+8 if ≥3 supporting articles, +4 if ≥2** (`supporting_article_count` —
  also inherited from clustering) — a related but distinct signal from
  raw source count, since one source can occasionally publish multiple
  pieces on the same story.
- **±10 signal-quality adjustment**: +10 at signal ≥85, +5 at ≥70, −10
  below 50 — a very low signal score (thin content, no urgency, unreliable
  source) should pull confidence down even if multiple weak sources happen
  to cover it.
- Clamped to `[15, 100]` — confidence is never reported as literally zero
  (a suppressed noise-tier event never reaches this layer at all, so
  anything that does get here has *some* baseline legitimacy) or as a
  false 100 (nothing in a rule-based system should claim certainty).

**Why this lives in Cognitive and not Intelligence**: `signal_score`
(Phase 25) answers "how important/urgent is this," a fundamentally
different question from `confidence` (Phase 27) — "how sure are we this
classification is right." Conflating them into one number would have made
Phase 25's score simultaneously mean two things depending on context,
which is exactly the kind of ambiguity Phase 25's four-independently-
capped-components design (§1.2) was built to avoid in the first place.

### 3.4 Why Cognitive is a thin layer over Briefing, not a rewrite

`build_cognitive_block()`'s first two output fields (`headline`,
`what_happened`) are copied verbatim from the input narrative block — this
layer is explicitly additive, never replacing or reinterpreting
Briefing's prose. Every Cognitive-mode field is derived, but every
Cognitive-mode *narrative* field is inherited unchanged. This mirrors the
whole stack's governing pattern: each phase adds a bounded set of new
fields on top of the previous phase's full output, rather than each phase
re-deriving everything from raw articles independently (which would have
meant four separate, potentially-inconsistent readings of "what is this
event about").

---

## 4. Phase 28 / 28B — Unified Feed

**Module:** `app/feed/` (`service.py`, `normalizer.py`, `routes.py`)
**Endpoints:** `GET /feed` (auto mode — **the endpoint the shipped mobile
app actually calls**), `GET /daily-feed?mode=` (explicit mode,
debugging/admin), `POST /admin/feed/cache/clear`
**Calls internally:** all three layers above, plus a raw DB read for
`mode=raw`

### 4.1 Problem

By the time Phase 27 shipped, there were four different ways to read a
topic's articles (`/daily-report` legacy, `/daily-intelligence`,
`/daily-briefing`, `/daily-cognitive`), each a different depth/shape. Per
the Project Principles' "business logic lives in the backend," the mobile
client should not be the one deciding which of four endpoints to call and
in what order to retry — Phase 28 collapses this into one endpoint that
decides depth server-side and never returns nothing if *any* mode has
data.

### 4.2 Auto mode selection (`_select_mode()`)

Priority order, first match wins:

1. **`X-Client-Type: mobile` header** → `cognitive`. This is what the
   shipped mobile app sends on every `/feed` call (`useDailyReport.ts`),
   so in practice this rule alone decides the mode for 100% of real mobile
   traffic — the remaining rules exist for non-mobile/API clients.
2. **Investor/market topic keywords** (`_INVESTOR_TOPIC_KEYWORDS` — market,
   finance, crypto, banking, inflation, etc.) → `cognitive`, regardless of
   client. The reasoning: someone reading a Markets or Finance topic wants
   the impact/risk/confidence framing even from a desktop browser, where
   the *client-type* heuristic below would otherwise pick the lighter
   `briefing` mode.
3. **Mobile User-Agent regex** → `cognitive` (fallback for a mobile client
   that didn't send the explicit header).
4. **Any other User-Agent** (desktop) → `briefing` — the narrative layer
   without cognitive framing, judged more scannable on a larger screen
   where a reader can take in more prose at once.
5. **No User-Agent at all** (API clients, curl, internal tooling) →
   `briefing` as a safe, always-available default.

`mode=auto` on the explicit `/daily-feed` endpoint always expands to
`cognitive` directly (no client-detection heuristics there — that endpoint
is for debugging/admin use, where the caller should get the deepest mode
by default rather than a guessed one).

### 4.3 Fallback chain — the reason `/feed` (almost) never returns empty

`_FALLBACK_CHAIN = ["cognitive", "briefing", "signal", "raw"]`. After mode
selection, `get_auto_feed()` tries the selected mode first; if it returns
zero items, it walks the rest of the chain **in this fixed order**
(regardless of which mode was originally selected) until one produces
items, or all four are exhausted. `raw` — a direct, no-scoring-no-
clustering read of `articles` — is deliberately the last resort: it's the
only mode with no noise suppression, so it's the correct floor (some
content beats none) but never the first choice.

This exists because noise suppression is a real risk to leaf cases: a
topic with only 1–2 assembled articles, all scoring below the 40 noise
threshold, would return **zero** events from `cognitive`/`briefing`/
`signal` even though `raw` mode would happily show those same 1–2
articles unscored. Rather than accept an empty feed as correct behavior
in that edge case, the fallback chain guarantees *some* content whenever
*any* assembled articles exist for the topic that day.

### 4.4 Date resolution — a second, independent fallback

Separately from mode fallback: when no `date` param is given, `/feed`
resolves to the **latest available report date** for the topic
(`_resolve_report_date()`), not blindly "today." Without this, a topic
whose newest pipeline run happened to fail assembly (or ran late) would
show nothing for "today" even though yesterday's content is still valid
and available — this is the same "serve stale-but-real content over
nothing" philosophy as the fallback chain above, applied to the date
dimension instead of the mode dimension. A short 60s in-memory
`_DATE_CACHE` avoids a DB round-trip on every cache-hit request (shorter
than the 300s response cache's own TTL specifically so a fresh pipeline
run within that window is picked up promptly rather than serving a
minutes-stale "latest date" for up to 5 more minutes).

### 4.5 Response caching

A 300-second in-memory `_CACHE`, keyed on `topic|resolved_date|mode_selected`
— **only non-empty results are cached** (`if items: _cache_set(...)`), so a
transient empty result (e.g. a DB hiccup mid-request) is never
accidentally pinned in the cache for the full TTL. `POST
/admin/feed/cache/clear` exists for exactly the case where stale content
needs to be forced out immediately, such as after a manual backfill. The
startup-time proactive warmup
(`_feed_cache_warmup()`, `app/startup_tasks.py`) pre-populates this same
cache for every active topic so the *first* real user request of the day
doesn't pay the uncached latency cost.

### 4.6 Normalization (`normalizer.py`)

Each of the four modes (`raw`/`signal`/`briefing`/`cognitive`) has its own
native shape (a raw article row vs. an intelligence event vs. a narrative
block vs. a cognitive block). `normalizer.py`'s four `normalize_X()`
functions map each into one **shared item shape** so the mobile client's
rendering code doesn't need to branch on which mode actually served the
response — it always receives the same field set (with mode-specific
fields simply absent/null when not applicable). This is the layer that
previously had a `body_text` propagation bug: `normalize_briefing()`/
`normalize_cognitive()` initially didn't read `body_text` off the lead
article at all, silently losing it exactly at this shape-conversion step
even though every layer below it had the field the whole time.

### 4.7 The "All" cross-topic mode

A special case inside both `get_daily_feed()`'s and `get_auto_feed()`'s
topic handling: `topic == "All"` skips mode selection entirely and always
serves `raw` mode across every active topic's top-scoring articles
(ranked by editorial `importance_score` then recency, capped at 200 total
— roughly 10 per topic × 20 topics). This is deliberately **not** run
through Intelligence/Briefing/Cognitive — clustering and signal scoring
are computed *within* a topic's own article pool; running them across all
20 topics' combined pool at once would cluster/score unrelated stories
from different domains against each other, which isn't a meaningful
operation. "All" is a browse view, not an intelligence view.

---

## 5. Cross-cutting design decisions

### 5.1 Why four phases instead of one big "intelligence layer"

Each phase has a genuinely distinct responsibility (score+dedupe / narrate
+connect / frame-for-action / route+cache) and, critically, each is
**independently useful and independently testable** — `/daily-intelligence`,
`/daily-briefing`, and `/daily-cognitive` all still exist as real,
directly-callable endpoints, not just internal implementation details of
`/feed`. This was a deliberate product/engineering choice, not scope
creep: an admin debugging a bad signal score can call
`/daily-intelligence` directly and see raw scores without narrative
prose or cognitive framing in the way; the shipped mobile app never calls
any of the three directly, but they remain first-class endpoints. Each
phase's test file (`test_intelligence.py`, `test_briefing.py`,
`test_cognitive.py`, `test_feed.py`) exercises its layer independently
with the layer below it mocked, matching this modularity.

### 5.2 Why every layer takes `topic` + optional `report_date`, never a
user id or device id

None of these four phases are personalized — same principle as the rest
of this product pre-auth (Phase 18's "Local-first bookmarks... Never
require auth for core read functionality"). A signal score, an event
cluster, or a cognitive frame is the same for every reader of a given
topic on a given day. This keeps every layer's caching (Phase 28's
`_CACHE`) trivially shareable across all requests for the same
topic+date+mode, rather than needing a per-user cache dimension.

### 5.3 Performance

`briefing/service.py`'s own docstring states a design target directly:
"Performance target: <20ms per topic (in-process, no DB writes, no LLM)."
This is achievable specifically *because* nothing in this stack does I/O
beyond the one DB read at the very bottom (Intelligence's article fetch)
— everything above that is pure in-memory Python over already-fetched
rows. Phase 28's `elapsed_ms` field in every response's `meta` block
makes this measurable on every real request, not just asserted in a
docstring.

### 5.4 What would need to change to add a fifth layer

The pattern is now established enough to extend: a hypothetical Phase 29
layer would (a) take one of the four existing layers' output shape as
input, (b) add a bounded set of new fields without mutating or dropping
the input's own fields, (c) write to no table, (d) get its own
`get_daily_X()` service function and `GET /daily-X` endpoint independent
of `/feed`, and (e) only get wired into `/feed`'s mode selection/fallback
chain as a deliberate, separate decision once the standalone endpoint is
validated — exactly how Cognitive was added on top of an already-shipped,
already-endpoint-exposed Briefing.

### 5.5 Relationship to Phase 19 (topic expansion) and Phase 24/24.2 (feed
reliability)

These two earlier phases are prerequisites, not part of this architecture
themselves, and don't need their own design doc at this depth — they're
scale/ops work (more topics, more sources, automated feed health
tracking), not a new read-time reasoning layer:

- **Phase 19** expanded the topic count from 10 to 20 and added the
  matching RSS sources — a data/config change (`migrations/0016` and
  `0027`, ~100+ new `news_sources` rows), not an architectural one. It
  matters here only in that Phase 25's per-topic computation now runs
  across double the topics it originally would have.
- **Phase 24/24.2** added the `news_sources` reliability columns
  (`success_count`, `failure_count`, `feed_state`, etc.) and the
  auto-disable/auto-recover lifecycle logic in `ingestion/service.py`.
  Phase 25's `credibility_score` component (§1.2) is the direct reason
  those columns exist beyond their original feed-health purpose — without
  Phase 24 already tracking per-source success/failure, Intelligence
  would have had no reliability signal to read at all.

---

## 6. Testing

All four layers are covered by DB-mocked unit tests — no test in any of
`test_intelligence.py`, `test_briefing.py`, `test_cognitive.py`,
`test_feed.py` hits a real Supabase instance (see each file's own
docstring). Coverage per layer: pure scoring/clustering/building functions
tested directly against constructed input dicts (no DB involved at all),
plus a service-level test per layer with `get_connection` mocked, plus a
route-level test via `TestClient` for HTTP status/shape. Phase 28's fallback
chain and cache behavior (empty-mode fallback, cache hit/miss, cache-clear
endpoint, the "All" topic special case) are tested explicitly in
`test_feed.py`, since that's the one layer with meaningfully complex
control flow (the other three are closer to straight-line transformations).
