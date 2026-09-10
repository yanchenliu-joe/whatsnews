# Phase 19 — Topic Expansion (10 → 20)

**Status:** complete
**Written:** 2026-07-13 — retrospective, reconstructed from migrations and
the implementation; no design document existed when this phase shipped.

## Goal

Grow topic coverage from the original 10 topics to 20, with matching RSS
source additions, so the product covers a broader range of daily-briefing
categories (Science, Crypto, Real Estate, Politics, Space, Education,
Labor, Sports, Entertainment, Transportation) alongside the original 10
(AI, Climate Change, Technology, Markets, Geopolitics, Healthcare, Energy,
Cybersecurity, Business, Defense).

## What changed

- **`topics` table**: 10 new rows (`is_active = TRUE`, `sort_order`
  continuing the existing sequence).
- **`news_sources` table**: ~50 new RSS feed rows across the 10 new
  topics, plus later additions (Phase 24.1A added ~100 more across *all*
  topics, old and new, bringing the total toward ~200, and Phase 25 added
  more still toward ~300 — topic expansion and source-count growth are
  two separate, overlapping efforts, not one single event).
- **Migration housekeeping (2026-07-13, same day as the Phase 25–28
  doc)**: this phase's own migration file was originally numbered `0016`
  and collided with an unrelated `articles.image_url` migration also
  numbered `0016` — renamed to `0027` via `git mv` (content unchanged,
  already applied to production under the old filename). See
  `ENGINEERING.md` for the current migration note.

## Why this needed no architectural changes

Every downstream system (assembly's per-topic candidate pool, the
editorial engine, WIM generation, the narrative/perspective/watch-next
generation stages, and later the entire Phase 25–28 intelligence/briefing/
cognitive/feed stack) is already parameterized by topic — none of it
hardcodes a topic count or topic list. Adding 10 rows to `topics` and
~50+ rows to `news_sources` was sufficient on its own; no code changes
were required in the pipeline, only more data for it to process. This is
the same reason `mobile/src/utils/topicsList.ts`'s `ALL_TOPICS` constant
(the mobile onboarding topic picker's source list) is the one place that
*does* need to be kept in sync manually — it's a plain hardcoded
`string[]`, not derived from the backend's `GET /topics` response, and
nothing enforces the two stay aligned (a known, accepted gap, not
revisited here).

## Downstream impact worth knowing about

- **Pipeline duration scales with topic count.** Every pipeline stage
  that loops per-topic (ingestion, editorial engine, WIM, narrative
  inputs) now does roughly double the work per run compared to the
  original 10-topic baseline. This is the direct reason later phases
  (the 2026-07-06 "Speed optimization pass," 2026-07-09's "Speed
  optimization pass #2") had real concurrency-tuning work to do — none of
  which would have mattered as much at the original 10-topic scale.
- **Phase 25's per-topic signal scoring/clustering** (see
  `docs/phase25-28-intelligence-feed-design.md` §5.5) inherits this
  scaling directly — twice the topics means twice the independent
  scoring/clustering passes per pipeline run, though each pass is still
  bounded to its own topic's article pool (never cross-topic), so this is
  linear scaling, not combinatorial.

## Verification

No special verification beyond the general pipeline health checks —
`GET /topics` returns 20 active rows; `GET /admin/topic-status` shows a
row per topic; a full `POST /admin/run-pipeline` run processes all 20
without needing any topic-count-specific configuration.
