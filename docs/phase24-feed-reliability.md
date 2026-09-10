# Phase 24 / 24.2 — Feed Reliability Tracking + Lifecycle State

**Status:** complete
**Written:** 2026-07-13 — retrospective, reconstructed directly from
`app/ingestion/service.py` and migrations `0017`/`0019`; no design doc
existed for this phase when it shipped (see Technical Debt #13).
**Prerequisite:** Phase 19 (topic/source expansion — this phase exists
largely *because of* the scale that expansion introduced: ~300 RSS feeds
means feed failures are a routine, ongoing operational reality, not an
edge case worth handling by hand).

## Goal

With ~300 RSS feeds across 20 topics, individual feeds inevitably go
stale, get rate-limited, change URLs, or disappear entirely — with no
tracking, a dead feed silently contributes zero articles forever with no
signal anywhere that it needs attention. Phase 24 adds per-feed
success/failure tracking (24.1) and a lifecycle state machine that acts on
that tracking automatically (24.2), so degraded feeds get throttled and
chronically-broken feeds get disabled without a human watching every one
of ~300 feeds by hand.

## Schema (migrations `0017`, `0019`)

`news_sources` gained, in two migrations:

**24.1 — raw counters** (`failure_count`, `success_count`,
`consecutive_failures`, `consecutive_successes`, `last_success_at`,
`last_failure_at`, `auto_disabled_at`).

**24.2 — lifecycle state** (`feed_state` — `active` / `degraded` /
`paused` / `disabled`, `skip_next_run`, `replace_flag`, `replace_reason`).

## The state machine

Applied via `_update_feed_reliability_batch()` (`app/ingestion/service.py`)
after every fetch pass — a single batched `UPDATE ... WHERE id = ANY(%s)`
per success/failure group, not one connection per source. This avoids
opening hundreds of short-lived connections during one ingestion run.

- **On success**: increments `success_count`/`consecutive_successes`,
  resets `consecutive_failures` to 0. If the feed was `degraded` (or had
  `auto_disabled_at` set) and has now reached **3 consecutive successes**,
  it recovers — `feed_state` → `active`, `is_active` → `TRUE`,
  `auto_disabled_at` cleared. A `degraded` feed that hasn't yet hit 3
  consecutive successes gets `skip_next_run = TRUE` (see throttling,
  below).
- **On failure**: increments `failure_count`/`consecutive_failures`,
  resets `consecutive_successes` to 0. At **3 consecutive failures**,
  `feed_state` transitions `active` → `degraded`. At **5 consecutive
  failures**, the feed auto-disables (`is_active = FALSE`,
  `auto_disabled_at = NOW()`) — but only if it has a success history
  (`success_count > 0`) or has existed for 24+ hours; a brand-new feed
  that fails its first 5 fetches in a row (e.g. a bad URL entered by an
  admin minutes ago) isn't auto-disabled before it's had a fair chance,
  since `created_at < NOW() - INTERVAL '24 hours'` is false for it yet
  and it has no prior success either.

## Throttling degraded feeds (`_load_active_topic_groups`)

A `degraded` feed isn't fetched at full frequency — `skip_next_run`
alternates it between being fetched and being skipped on successive
pipeline runs, halving the load a known-flaky feed puts on the ingestion
pass while still giving it a chance to recover (each fetch it *does*
participate in still counts toward the 3-consecutive-successes recovery
threshold above). `paused` and `disabled` feeds are excluded from every
run's `news_sources` query entirely — `paused` is an admin/throttle state
that's never auto-resumed by the pipeline itself (only an explicit
`POST /admin/feeds/{id}/enable`/`promote` call moves it out), `disabled`
is the same as `is_active = FALSE`.

## Admin surface

`app/admin/feed_diagnostics_routes.py` (`GET /admin/feed-health`,
`GET /admin/rss-scale-audit`, `GET /admin/rss-bottlenecks`) and
`app/admin/feed_lifecycle_routes.py` (`POST /admin/feeds/{id}/test|
disable|enable|pause|promote|replace-mark`) — the latter lets an admin
override the state machine directly (e.g. manually pause a feed pending
investigation, or force-recover one early) rather than only ever waiting
for the automatic thresholds. `app/admin/feed_recommendation_routes.py`
(`GET /admin/feed-recommendations`, `/admin/topic-rebalancing`) is a
separate, advisory-only layer built on top of these same reliability
columns — see its own docstrings; it never mutates state itself.

## Why Phase 25's `credibility_score` depends on this phase directly

Phase 25 (Intelligence — see `docs/phase25-28-intelligence-feed-design.md`
§1.2) reuses these exact `success_count`/`failure_count` columns for a
second, unrelated purpose: a per-article `credibility_score` component
reflecting how trustworthy the *source* has historically been. One set of
counters, two consumers (feed *health* here, reader-facing *trust* there)
— without this phase's tracking already existing, Phase 25 would have had
no reliability signal to read at all.

## Verification

`GET /admin/feed-health` groups every feed by topic with its current
`feed_state` and computed health status; `GET /admin/system-status` isn't
related to this (that's pipeline/scheduler status, not feed health).
`tests/test_ingestion_reliability.py` covers the batched UPDATE's CASE
branches (which branch fires with which params) and
`_load_active_topic_groups`'s degraded/paused suppression — Postgres
itself evaluates the CASE expressions, so the tests lock in intent, not a
live-database guarantee (see Technical Debt #11's note on this same
limitation for a related test file).
