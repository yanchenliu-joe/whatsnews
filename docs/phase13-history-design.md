# Phase 13 — Historical Briefings Design

**Status:** Implemented — see [phase13-implementation.md](./phase13-implementation.md)  
**Last updated:** 2025-06-26  
**Scope:** Phase 13.0 — browse, calendar, and basic search over past daily briefings

---

## 1. Product Goals

### Mission alignment

WhatsNews is an **AI Daily Intelligence Briefing**, not a news reader. Historical Briefings must help users answer:

> "What happened on that day, and why did it matter?"

—not merely "what articles existed in the feed."

### Primary goals

| Goal | Description | Success signal |
|------|-------------|----------------|
| **Retention** | Users return to prior days to catch up or re-read context | Repeat opens on non-today dates |
| **Understanding over time** | Users can compare days and topics without leaving the app | Date navigation used across multiple topics |
| **Trust** | Archived briefings match what was published that day | Same articles + `why_it_matters` as export for that date |
| **Discoverability** | Users find past stories via calendar and search | Search and calendar events in analytics |

### Non-goals (Phase 13)

- User accounts, per-user history, or personalized archives
- Recommendation engine ("you might like…")
- Re-generating or editing past briefings from the mobile app
- Rich PDF archive UX (admin export already supports `date=`)
- Deployment, public beta, or production hardening
- Full-text search infrastructure (Elasticsearch, etc.)

### Product principles (gates)

Every Phase 13 feature must pass:

1. **Does this improve understanding?** — Archive shows full briefing with Why It Matters, not headline lists.
2. **Does this improve daily habit?** — History supports catch-up and continuity, not distraction.
3. **Does this strengthen the briefing experience?** — Same editorial card UI as today; date is the only new axis.

---

## 2. User Flows

### Flow A — Default open (today)

1. User opens app → `BriefingScreen` loads latest briefing for default/first topic.
2. Header shows today's date; section label reads **Today's Briefing**.
3. Behavior is identical to Phase 12 (no regression).

### Flow B — Browse previous day (per topic)

1. User selects a topic in `TopicSwitcher`.
2. User taps **◀** on `DateNavigator`.
3. App requests briefing for `topic + previous_date_with_content`.
4. UI switches to **Archive Briefing** label; date shows full weekday.
5. User reads articles with same `ArticleCard` + `WhyItMattersBlock`.
6. User taps **Jump to today** → returns to latest briefing for current topic.

**Skip-empty behavior:** Prev/next skips dates with no publishable briefing (no articles with `why_it_matters`), using `/briefing-dates` as the navigation index.

### Flow C — Calendar picker

1. User taps calendar icon on `DateNavigator`.
2. App loads `/briefing-dates?topic=<selected>&limit=90`.
3. Modal shows month grid; days with briefings show a dot.
4. User taps a dotted day → modal closes, briefing loads for that date.
5. Gray days (no briefing) are not selectable.

### Flow D — Cross-day search (Phase 13b)

1. User taps search icon in header.
2. User types query (min 3 characters).
3. App calls `/briefing-search?q=...` (optional `topic` filter).
4. Results show title, topic, date, snippet.
5. User taps result → navigates to `BriefingScreen` with `topic + date`; optionally scrolls to matching article (stretch goal).

### Flow E — Topic switch while viewing archive

1. User is viewing Technology on 2025-06-18.
2. User switches to Markets in `TopicSwitcher`.
3. **Default:** load latest briefing for Markets (today behavior).
4. **Alternative (defer):** keep date if Markets has a briefing on 2025-06-18; else latest. **Decision: default to latest on topic switch** — simpler mental model; document in UX.

### Flow F — Pull to refresh

1. User pulls to refresh on archive date.
2. App re-fetches same `topic + date` (historical data is stable).
3. Selected date does **not** reset to today.

### Flow G — Saved articles (unchanged, minor enhancement later)

- Saved articles remain URL-keyed locally.
- Phase 13c: optionally show `report_date` on saved items if metadata was captured at save time.

---

## 3. Database Model

### 3.1 Current schema (sufficient for Phase 13)

Historical briefings are already stored implicitly:

```
topics
  └── daily_reports (topic_id, report_date) UNIQUE(topic_id, report_date)
        └── articles (report_id, title, summary, why_it_matters, …)
```

**`daily_reports`** — one row per topic per calendar day. `report_date` is the briefing date (assembly/generation day), not article `published_at`.

**`articles`** — candidate pool (`report_id IS NULL`) or assigned to a report (`report_id` set). Assembly only rewrites **today's** report; past `report_date` rows are not cleared.

### 3.2 Publishable briefing definition

A date is **publishable** for a topic when:

```sql
EXISTS (
  SELECT 1 FROM articles a
  WHERE a.report_id = dr.id
    AND a.why_it_matters IS NOT NULL
    AND TRIM(a.why_it_matters) != ''
)
```

Calendar, navigation, and public API use this rule. Aligns with export quality gate (export blocks missing `why_it_matters`; archive may show partial briefings with a warning — **decision: archive uses publishable rule only**).

### 3.3 Phase 13 schema changes

| Change | Required? | Notes |
|--------|-----------|-------|
| New `briefing_snapshots` table | **No** | Relational linkage is the snapshot (see §6) |
| New columns on `daily_reports` | **No** for 13a | Optional `headline TEXT` in Phase 15 |
| Index on `daily_reports(report_date DESC)` | Optional | Unique `(topic_id, report_date)` already indexes per-topic lookups; add if global calendar is slow |
| FTS on `articles` | **No** for search Phase 1 | `ILIKE` sufficient at current scale |

### 3.4 Optional future columns (not Phase 13)

| Table | Column | Phase | Purpose |
|-------|--------|-------|---------|
| `daily_reports` | `headline` | 15 | AI day summary for archive cards |
| `daily_reports` | `meta_json` | 14–15 | Voice URL, generation metadata |
| `articles` | `search_vector` | 13c+ | PostgreSQL `tsvector` if `ILIKE` degrades |

### 3.5 Data retention

- No automatic deletion in Phase 13.
- Document operator expectation: briefings are permanent once `report_id` is set and assembly has moved on.
- Future: optional retention job for unassigned candidates (`report_id IS NULL`), not for assigned archive articles.

### 3.6 Inactive topics

- `topics.is_active = FALSE` → hidden from today's `TopicSwitcher`.
- Historical briefings for inactive topics remain in DB.
- **Decision:** no dedicated inactive-topic browser in 13a; data preserved for admin/export and future use.

---

## 4. Backend API Design

### 4.1 Design principles

- Extend existing endpoints; avoid parallel read paths.
- Same response shapes as today where possible (`DailyReport`).
- Share load logic with export (`ExportBundle` / `load_exportable_briefing`) via a common briefing loader module.
- No auth on public read endpoints (consistent with Phase 12).
- FastAPI + synchronous DB access (existing pattern).

### 4.2 `GET /daily-report` (extend)

**Existing:** `?topic=<name>` → latest report for topic.

**Add:** `?date=YYYY-MM-DD` (optional).

| Parameter | Rule |
|-----------|------|
| `topic` | Strongly recommended; 404 if missing/invalid/inactive for *today* path |
| `date` | Optional; ISO date; 400 if invalid or future |
| `date` omitted | `ORDER BY report_date DESC LIMIT 1` (backward compatible) |

**Response** — extend current shape:

```json
{
  "date": "2025-06-20",
  "topic": "Technology",
  "is_latest": false,
  "items": [
    {
      "title": "...",
      "summary": "...",
      "source": "...",
      "url": "...",
      "why_it_matters": "...",
      "published_at": "2025-06-19T14:00:00+00:00"
    }
  ]
}
```

| Status | Condition |
|--------|-----------|
| 200 | Publishable briefing found |
| 404 | Topic not found, inactive (today path), or no publishable briefing for date |
| 400 | Bad date format or future date |
| 503 | Database error |

**Ordering:** `compute_importance_score` descending (same as today and export).

**Article cap:** `MAX_ARTICLES_PER_REPORT` (5).

**Mock mode** (no `DATABASE_URL`): latest only; historical `date` → 404.

### 4.3 `GET /briefing-dates` (new)

Lists dates with publishable briefings for calendar and prev/next navigation.

```
GET /briefing-dates?topic=Technology&limit=90
GET /briefing-dates?limit=90
```

| Parameter | Default | Rule |
|-----------|---------|------|
| `topic` | — | If set, scope to one topic |
| `limit` | 90 | Max dates returned (cap 365) |

**Response (single topic):**

```json
{
  "topic": "Technology",
  "dates": [
    { "date": "2025-06-26", "article_count": 5 },
    { "date": "2025-06-25", "article_count": 4 }
  ],
  "earliest": "2025-03-15",
  "latest": "2025-06-26",
  "count": 42
}
```

**Response (all topics):**

```json
{
  "topic": null,
  "dates": [
    { "date": "2025-06-26", "topics_available": 10, "total_articles": 48 }
  ],
  "earliest": "...",
  "latest": "...",
  "count": 42
}
```

### 4.4 `GET /briefing-search` (new — Phase 13b)

Search Phase 1 only (see §7).

```
GET /briefing-search?q=nvidia&topic=Technology&limit=20&offset=0
```

| Parameter | Rule |
|-----------|------|
| `q` | Required, min length 3 |
| `topic` | Optional filter |
| `limit` | Default 20, max 50 |
| `offset` | Default 0 |

**Response:**

```json
{
  "query": "nvidia",
  "total": 3,
  "limit": 20,
  "offset": 0,
  "results": [
    {
      "date": "2025-06-18",
      "topic": "Technology",
      "title": "...",
      "source": "...",
      "url": "...",
      "why_it_matters": "...",
      "snippet": "...matched context..."
    }
  ]
}
```

### 4.5 Admin APIs (no changes)

- `GET /admin/export/briefing?date=YYYY-MM-DD` already exports historical briefings.
- Operator Console unchanged for Phase 13.

### 4.6 Internal module layout (implementation guide)

```
backend/app/briefing/
  loader.py      # load_briefing(cur, topic_name, report_date=None) -> BriefingBundle
  dates.py       # list_briefing_dates(cur, topic_name=None, limit=90)
  search.py      # search_briefings(cur, q, topic_name=None, limit, offset)
  models.py      # BriefingBundle, BriefingItem (mirror mobile DailyReport)
```

`export/loader.py` should call `briefing/loader.py` or share a single source to prevent drift.

### 4.7 Analytics (product_events)

| event_name | metadata |
|------------|----------|
| `briefing_date_changed` | `topic_name`, `from_date`, `to_date`, `direction` |
| `briefing_archive_viewed` | `topic_name`, `report_date` |
| `briefing_search` | `query`, `result_count` |
| `briefing_jump_to_today` | `topic_name`, `from_date` |

---

## 5. Frontend Navigation and UX

### 5.1 Stack and patterns

- Expo React Native (existing).
- Screen enum in `App.tsx`: `"main" | "admin" | "saved"` → add `"search"` in 13b.
- Hooks for data: `useDailyReport`, `useBriefingDates`, `useBriefingSearch`.
- Reuse: `ArticleCard`, `WhyItMattersBlock`, `TopicSwitcher`, state components.

### 5.2 State model

```typescript
// App-level state (main screen)
selectedTopic: string
selectedDate: string | null   // null = latest for topic
briefingDates: BriefingDatesResponse | null  // cached per topic
```

| State change | Behavior |
|--------------|----------|
| Topic change | Reset `selectedDate` to `null` (load latest) |
| Date change | Keep topic; fetch `daily-report` with `date` |
| Jump to today | `selectedDate = null` |
| App cold start | `selectedDate = null` |

### 5.3 Layout (BriefingScreen)

```
┌──────────────────────────────────────────┐
│ WhatsNews          [Saved] [Search] [↻]  │
│ Updated 3 min ago                        │
├──────────────────────────────────────────┤
│ TopicSwitcher (horizontal chips)           │
├──────────────────────────────────────────┤
│  ◀   Thursday, June 20, 2025   ▶   📅   │  DateNavigator
│  [Today]  (shown only when archive)      │
├──────────────────────────────────────────┤
│ Archive Briefing · 5 stories             │  SectionHeader
├──────────────────────────────────────────┤
│ ArticleCard × N                          │
├──────────────────────────────────────────┤
│ ─── End of briefing ───                  │
└──────────────────────────────────────────┘
```

### 5.4 Components

| Component | Phase | Responsibility |
|-----------|-------|----------------|
| `DateNavigator` | 13a | Prev/next, formatted date, opens calendar |
| `CalendarPicker` | 13b | Modal month grid with availability dots |
| `SearchScreen` | 13b | Query input + result list |
| `useBriefingDates` | 13a | Fetch and cache `/briefing-dates` |
| `useDailyReport(topic, date?)` | 13a | Extend existing hook |

### 5.5 Visual language

| Context | Section header | Date line | Footer |
|---------|----------------|-----------|--------|
| Latest (`is_latest: true`) | Today's Briefing | "Today" or full date | You're all caught up |
| Archive | Archive Briefing | Full weekday date | End of briefing |

Use existing theme tokens (`colors`, `spacing`, `typography`). Optional: slightly muted section header for archive (13c polish).

### 5.6 Empty and error states

| Case | UI |
|------|-----|
| No briefing for date | EmptyState: "No briefing was published on this date." |
| Network error | ErrorState with retry (same date) |
| Search &lt; 3 chars | Inline hint, no request |
| Search no results | EmptyState: "No stories match your search." |
| Calendar loading | Spinner in modal |

### 5.7 Mobile caching

```typescript
// In-memory cache for session
reportCache: Map<string, DailyReport>  // key: `${topic}:${date|null}`
datesCache: Map<string, BriefingDatesResponse>  // key: topic name
```

Historical reports are immutable → cache indefinitely within session. Clear on topic change only for dates cache refresh if needed.

### 5.8 Accessibility

- DateNavigator buttons: accessibility labels ("Previous briefing", "Next briefing", "Choose date").
- Calendar days: label includes date and whether briefing exists.

---

## 6. Snapshot Storage Strategy

### 6.1 Definition

A **briefing snapshot** is the immutable set of articles and their `why_it_matters` text that constituted a published daily briefing for one topic on one `report_date`.

### 6.2 Strategy: relational implicit snapshots (Phase 13)

**Do not introduce a separate snapshot store for Phase 13.**

The snapshot is:

```
daily_reports(id, topic_id, report_date)
  → articles WHERE report_id = daily_reports.id
```

**Why this is sufficient:**

1. Assembly only clears/reassigns articles for **today's** `report_id` (`clear_report_articles` scoped to current run).
2. Past `daily_reports` rows are never deleted by the pipeline.
3. Articles assigned to past reports keep their `report_id` until explicit deletion.
4. `why_it_matters` is stored on the article row at generation time.
5. Global `content_hash` dedup prevents duplicate article rows; reassignment to a new day unlinks from today (`report_id = NULL`) but does not remove historical links on past reports.

### 6.3 Consistency with export

`ExportBundle` loads the same `(topic_id, report_date)` + `articles.report_id` graph. Historical briefings in the app must match admin JSON/PDF export for the same date.

### 6.4 Snapshot immutability guarantees and gaps

| Guaranteed | Gap | Mitigation |
|------------|-----|------------|
| Past reports not re-assembled | Manual DB edits | Ops discipline; no admin "re-run assembly for date" in 13 | 
| `why_it_matters` preserved on re-selection | Article row updated if admin regenerates WIM for old report_id | Rare; only if admin targets old report |
| Export and read use same loader | Loader drift | Single `briefing/loader.py` |

### 6.5 When a separate snapshot table would be needed (future)

Consider `briefing_snapshots(report_id, snapshot_json JSONB, created_at)` if:

- Pipeline re-runs assembly for arbitrary past dates
- Article rows are shared across multiple reports without `report_id` isolation
- Legal/compliance requires byte-identical reproduction

**Not required for Phase 13–15** given current assembly design.

### 6.6 Voice briefing attachment (Phase 14 preview)

```
briefing_media (
  id SERIAL PRIMARY KEY,
  report_id INTEGER REFERENCES daily_reports(id),
  media_type TEXT,        -- 'audio'
  url TEXT,
  duration_seconds INTEGER,
  created_at TIMESTAMPTZ
)
```

Keyed by `report_id` → naturally historical. No change to article snapshot model.

---

## 7. Search Strategy (Phase 1 Only)

### 7.1 Scope

Phase 13b **Search Phase 1** — simple, no FTS infrastructure.

### 7.2 Query approach

PostgreSQL `ILIKE` on:

- `articles.title`
- `articles.summary`
- `articles.why_it_matters`

```sql
SELECT dr.report_date, t.name AS topic, a.title, a.source, a.url, a.why_it_matters
FROM articles a
JOIN daily_reports dr ON dr.id = a.report_id
JOIN topics t ON t.id = dr.topic_id
WHERE a.report_id IS NOT NULL
  AND TRIM(a.why_it_matters) != ''
  AND (
    a.title ILIKE %s OR
    a.summary ILIKE %s OR
    a.why_it_matters ILIKE %s
  )
  AND (t.name = %s OR %s IS NULL)  -- optional topic filter
ORDER BY dr.report_date DESC, a.id ASC
LIMIT %s OFFSET %s
```

Pattern: `%query%` with escaped `%` and `_`.

### 7.3 Snippet generation

Server-side: find first matching field; extract ~120 chars around match; prefix with ellipsis if truncated.

### 7.4 Limits and guardrails

| Rule | Value |
|------|-------|
| Min query length | 3 |
| Max `limit` | 50 |
| Max `offset` | 1000 |
| Rate limiting | Defer until deployment |

### 7.5 Scale expectations

| Metric | Estimate | Phase 1 OK? |
|--------|----------|-------------|
| Topics | 10 → 20 | Yes |
| Days archived | ~365 | Yes |
| Articles per day per topic | 5 | Yes |
| Total searchable rows | ~18,000 at 365×10×5 | Yes with `ILIKE` |

### 7.7 Phase 2 search (out of scope, documented for path)

When `ILIKE` exceeds ~100ms p95 or row count &gt; ~50k:

1. Add `articles.search_vector tsvector` (generated or trigger-maintained).
2. GIN index.
3. `to_tsquery` / `plainto_tsquery` with ranking.
4. Optional: highlight via `ts_headline`.

No external search service.

---

## 8. Future Compatibility

### 8.1 Voice Briefings (Phase 14)

| Concern | Compatibility |
|---------|---------------|
| Historical audio | `briefing_media` or `meta_json` on `daily_reports`, keyed by `report_id` |
| UI | `DateNavigator` unchanged; add play button when media exists for loaded date |
| API | Extend `daily-report` with optional `audio: { url, duration_seconds }` or separate `GET /briefing-media` |
| Snapshot | Audio is additive; article snapshot unchanged |

### 8.2 AI Intelligence Layer (Phase 15)

| Capability | How history helps |
|------------|-------------------|
| "Explain deeper" on archive article | `topic + date + article url` identifies context |
| "Compare today vs yesterday" | `briefing-dates` + two `daily-report` calls |
| "Summarize last week for Technology" | Date range loader (future `from_date`/`to_date` on API) |
| Day-level summary | `daily_reports.headline` or `meta_json.summary` populated at generation |

AI layer reads snapshots via `briefing/loader.py` — same source as UI and export.

### 8.3 Topic expansion (Phase 16, 15–20 topics)

| Concern | Impact |
|---------|--------|
| Calendar | Per-topic `briefing-dates`; no cross-topic explosion |
| Search | Row count grows linearly with topics; Phase 1 search still fine |
| TopicSwitcher | Already dynamic from `/topics` |
| Inactive topics | History preserved; not shown in switcher |

No schema change required for more topics.

---

## 9. Migration Strategy from Current Architecture

### 9.1 Phase map

| Step | Work | Risk |
|------|------|------|
| **13.0** | This design doc | — |
| **13.1** | `briefing/loader.py` + extend `/daily-report` | Low — backward compatible |
| **13.2** | `/briefing-dates` + mobile `DateNavigator` + hook | Low |
| **13.3** | `/briefing-search` + `SearchScreen` | Low |
| **13.4** | `CalendarPicker`, analytics, polish | Low |

### 9.2 Backend migration

- **No breaking API changes.** `GET /daily-report` without `date` behaves as today.
- **No required SQL migration** for 13a–13b.
- Optional index (run in Supabase if needed):

```sql
CREATE INDEX IF NOT EXISTS idx_daily_reports_report_date
    ON daily_reports (report_date DESC);
```

### 9.3 Mobile migration

- Extend `useDailyReport(selectedTopic, selectedDate?)` — default `null` preserves current behavior.
- `BriefingScreen` props add date navigation; no new root navigator required.
- `DailyReport` type add `is_latest?: boolean`.

### 9.4 Data backfill

- **None required.** Existing `daily_reports` + assigned articles are the archive.
- Run sanity SQL (below) to confirm depth before shipping UI.

### 9.5 Rollout

1. Ship backend date param + `/briefing-dates` first; verify with curl.
2. Ship mobile date navigation against new APIs.
3. Ship search after calendar stable.
4. No feature flags needed at current scale; optional `EXPO_PUBLIC_HISTORY_ENABLED` if desired.

### 9.6 Rollback

- Mobile: ignore `date` param client-side → back to today-only.
- Backend: new endpoints unused; extended `date` param optional.

---

## 10. Risks and Trade-offs

### 10.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Shallow archive (few days of data) | High early | Users see empty calendar | Clear empty states; archive grows with scheduler |
| Loader drift between export and `/daily-report` | Medium | Trust erosion | Single `briefing/loader.py` |
| `ILIKE` slow at scale | Low in Phase 13 | Slow search | Phase 2 FTS; limit + index on `report_date` |
| Topic switch resets date | By design | Mild confusion | UX copy; optional "same date" mode later |
| Inactive topic history inaccessible | Low | Data orphaned in UI | Admin export still works; revisit if needed |
| Mock mode hides history in dev | Medium | Dev/test gap | Document; use DB for history testing |

### 10.2 Trade-offs accepted

| Decision | Alternative rejected | Why |
|----------|---------------------|-----|
| Implicit relational snapshots | JSON snapshot per day | Simpler; matches export; assembly already isolates past days |
| Extend `/daily-report` | New `/briefing/history` resource | Fewer endpoints; mobile type unchanged |
| `ILIKE` search | Elasticsearch / dedicated search | Aligns with simple architecture |
| Reset date on topic change | Keep date across topics | Simpler state; fewer empty states |
| No auth on history | Per-user archive | No auth system yet; defer |
| 90-day calendar default | Full archive | Mobile performance; increase `limit` param later |
| Publishable = has `why_it_matters` | Any linked article | Matches product quality bar |

### 10.3 Open decisions (resolve before 13.2)

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Partial briefings (some articles missing WIM) in archive? | Hide; use publishable rule |
| 2 | `inactive` topic in archive browser? | Defer to 13c |
| 3 | Global vs per-topic calendar first? | Per-topic for 13b |
| 4 | `EXPO_PUBLIC_HISTORY_ENABLED` flag? | Optional; skip unless needed |

---

## Appendix A — Sanity SQL (pre-ship)

```sql
-- Archive depth per topic
SELECT t.name,
       COUNT(DISTINCT dr.report_date) AS days,
       MIN(dr.report_date) AS earliest,
       MAX(dr.report_date) AS latest
FROM daily_reports dr
JOIN topics t ON t.id = dr.topic_id
GROUP BY t.name
ORDER BY t.sort_order, t.name;

-- Publishable briefings (last 30 days)
SELECT dr.report_date, t.name, COUNT(a.id) AS articles
FROM daily_reports dr
JOIN topics t ON t.id = dr.topic_id
JOIN articles a ON a.report_id = dr.id
WHERE a.why_it_matters IS NOT NULL AND TRIM(a.why_it_matters) != ''
  AND dr.report_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY dr.report_date, t.name
ORDER BY dr.report_date DESC, t.name;
```

## Appendix B — Verification curl (post-implementation)

```bash
# Regression: latest
curl -s "http://localhost:8000/daily-report?topic=Technology" | jq '.date, .topic, (.items | length)'

# Historical
curl -s "http://localhost:8000/daily-report?topic=Technology&date=2025-06-20" | jq '.is_latest, .date'

# Calendar
curl -s "http://localhost:8000/briefing-dates?topic=Technology&limit=30" | jq '.count, .latest'

# Search (13b)
curl -s "http://localhost:8000/briefing-search?q=climate&limit=10" | jq '.total'
```

## Appendix C — Related files (current codebase)

| Area | Path |
|------|------|
| Schema | `backend/app/schema.sql` |
| Daily report API | `backend/app/main.py` (`GET /daily-report`) |
| Export loader | `backend/app/export/loader.py` |
| Assembly | `backend/app/assembly.py` |
| Mobile hook | `mobile/src/hooks/useDailyReport.ts` |
| Mobile screen | `mobile/src/screens/BriefingScreen.tsx` |
| Types | `mobile/src/types/index.ts` |
