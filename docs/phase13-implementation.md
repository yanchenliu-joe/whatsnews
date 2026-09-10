# Phase 13 — Historical Briefings Implementation Notes

**Status:** Complete (Phases 13.0–13.4)  
**Last updated:** 2025-06-26

This document summarizes what was built. The original design lives in [phase13-history-design.md](./phase13-history-design.md).

---

## Backend

### Shared module

`backend/app/briefing_repository.py` — single source of truth for loading publishable briefings.

**Publishable rule:** at least one article with non-empty `why_it_matters`.

### Endpoints

| Endpoint | Purpose | Empty behavior |
|----------|---------|----------------|
| `GET /daily-report?topic=` | Today / latest briefing (unchanged) | Mock or 404 |
| `GET /history?limit=&topic=` | Recent briefing summaries | `items: []` (200) |
| `GET /history/dates?limit=&topic=` | Date index for chips/calendar | `dates: []` (200) |
| `GET /history/date/{YYYY-MM-DD}` | All topics for one date | 404 if none publishable |
| `GET /history/topic/{name}?limit=` | Topic history by date | 404 if topic missing or empty |
| `GET /history/search?q=&limit=&offset=` | ILIKE keyword search | `total: 0` (200) |

Search: `q` trimmed, min 3 characters, max 100 characters. ILIKE on title, summary, why_it_matters, source (escaped patterns).

### Export reuse

`backend/app/export/loader.py` uses `briefing_repository` for report/article loading.

---

## Mobile frontend

### Navigation

- **Main screen:** Today's briefing via `/daily-report` (default).
- **History button** in header → `HistoryScreen` (lazy-loaded data).
- **Back** / **Today's briefing** return to main without affecting topic selection.

### History screen flow

1. Load `/history/dates` → horizontal date chips (latest selected by default).
2. Load `/history/date/{date}` → topic sections with `ArticleCard` + Why It Matters.
3. Search input → debounced 400ms → `/history/search?q=` → results with date + topic labels.
4. Clear search → returns to date browsing.

### Key files

| File | Role |
|------|------|
| `src/services/historyApi.ts` | API client |
| `src/hooks/useHistory.ts` | Dates + date detail |
| `src/hooks/useHistorySearch.ts` | Debounced search |
| `src/screens/HistoryScreenContainer.tsx` | Lazy mount + wiring |
| `src/screens/HistoryScreen.tsx` | UI |
| `src/components/DateChipRow.tsx` | Date chips |

### Analytics events

- `briefing_archive_viewed`
- `briefing_date_changed`
- `history_search_submitted`
- `history_search_result_opened`

---

## Verification commands

### Backend

```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

curl -s "http://localhost:8000/history?limit=5" | jq '.count'
curl -s "http://localhost:8000/history/dates?limit=10" | jq '.count, .latest'
curl -s "http://localhost:8000/history/date/2026-06-23" | jq '.topic_count'
curl -s "http://localhost:8000/history/topic/Technology?limit=5" | jq '.count'
curl -s "http://localhost:8000/history/search?q=tech&limit=5" | jq '.total'
curl -s "http://localhost:8000/daily-report?topic=Technology" | jq '.date, (.items|length)'
```

### Mobile

```bash
cd mobile && npx expo start
cd mobile && npx tsc --noEmit
```

---

## Current limitations (intentional)

| Item | Status |
|------|--------|
| Full month calendar UI | Deferred |
| Search pagination UI | Deferred (backend supports offset) |
| Topic filter in search UI | Deferred (backend supports `?topic=`) |
| PostgreSQL FTS | Deferred |
| AI / semantic search | Deferred (Phase 15) |
| Per-user history | No auth yet |
| `/daily-report` date param | Not added; history uses `/history/*` |

---

## Phase 14 handoff

Historical briefings are stable for Voice Briefing attachment via `report_id` / `daily_reports` without schema changes to the article snapshot model.
