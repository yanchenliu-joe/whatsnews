# WhatsNews Engineering Guide

This document describes the current architecture, operating model, and important
technical decisions for WhatsNews. It is intended to remain focused on the system
as it exists today rather than serve as a chronological development log.

## Architecture

WhatsNews is a daily news briefing product with two main applications:

- A FastAPI backend that ingests RSS feeds, selects and enriches articles, builds
  briefings, sends notifications, and serves the API.
- A React Native application built with Expo that presents the briefing, archive,
  reading tools, account settings, achievements, and on-device speech.

The main data path is:

```text
RSS feeds
  -> ingestion and normalization
  -> article selection
  -> editorial enrichment
  -> daily narrative generation
  -> PostgreSQL
  -> FastAPI endpoints
  -> mobile application
```

Supabase provides PostgreSQL, authentication, and object storage. The deployed
backend runs on Render. Mobile builds are produced with EAS.

## Backend

The backend is under `backend/` and targets Python 3.13.

Important entry points:

- `app/main.py` creates the FastAPI application, configures CORS and lifecycle
  tasks, and registers route modules.
- `app/pipeline/orchestrator.py` coordinates scheduled ingestion and generation.
- `app/pipeline/scheduler.py` calculates scheduled run times.
- `app/database.py` creates PostgreSQL connections.
- `app/public_routes.py` registers core public endpoints.
- `app/admin/` contains admin-only diagnostics and operations.
- `app/notifications/` handles push delivery and per-device scheduling.
- `app/retention/` implements automatic archive cleanup.

Business logic belongs in service modules. Route handlers should validate input,
call a service, and shape the response. SQL belongs in repository modules or in
the established data-access layer for that subsystem.

### API groups

Public endpoints include:

- `GET /health`
- `GET /topics`
- `GET /feed`
- `GET /daily-feed`
- `GET /daily-report`
- `GET /daily-intelligence`
- `GET /daily-briefing`
- `GET /daily-cognitive`
- `GET /narratives/latest`
- Archive and search endpoints under `/history`
- `GET /articles/related`
- Device registration and analytics endpoints

Authenticated endpoints include:

- `GET /auth/me`
- Preferences under `/me/preferences`
- Saved articles under `/me/saved-articles`
- Avatar updates under `/me/avatar`
- Entitlement reads under `/me/entitlement`

All `/admin/*` operations must require the `x-admin-key` header. Shared-secret
comparisons use constant-time comparison. Internal exception details are logged
server-side and should not be returned to public clients.

## AI Pipeline

The scheduled pipeline is fault-isolated by stage:

1. Fetch RSS feeds concurrently.
2. Normalize and deduplicate articles.
3. Assemble the best articles for each active topic.
4. Apply editorial metadata and importance signals.
5. Generate or refine “Why It Matters” text.
6. Build the daily perspective and watch-next content.
7. Build the cross-topic morning narrative.
8. Optionally generate server-side audio.
9. Send push notifications to eligible devices.

Text generation has deterministic rule-based fallbacks. The production system
does not require a paid text-generation key to produce its core briefing.
Server-side voice generation is currently disabled; the mobile application reads
the narrative with on-device speech.

The intelligence, briefing, cognitive, and feed packages are read-time layers,
not scheduled pipeline stages. They transform already-selected articles without
creating additional persistent pipeline state:

```text
selected articles
  -> signal scoring and event clustering
  -> narrative briefing blocks
  -> cognitive framing
  -> normalized feed response
```

`GET /feed` is the primary mobile feed endpoint. It selects an appropriate depth
and falls back to simpler response modes when a richer layer returns no items.

## Mobile

The mobile application is under `mobile/` and uses React Native, Expo, and
TypeScript.

Core structure:

- `App.tsx` defines the provider tree and application initialization.
- `src/navigation/` defines the root stack and bottom tabs.
- `src/screens/` contains full-screen views.
- `src/components/` contains reusable UI.
- `src/hooks/` owns data loading and stateful feature behavior.
- `src/services/` contains API and platform integrations.
- `src/context/` contains authentication, preferences, saved articles, reading
  progress, subscriptions, and achievements state.
- `src/theme/` contains shared visual tokens.
- `src/i18n/` contains the 12 supported interface languages.

The main bottom tabs are Briefing, Archive, Streak, and Account. The root stack
also provides article detail, search, saved articles, topic management, language
selection, sign-in, and badge screens.

### Mobile operating principles

- Core reading remains available without authentication.
- Preferences and saved articles are local-first and synchronize opportunistically.
- Network-backed content uses cache-then-refresh where appropriate.
- Features depending on unavailable native capabilities degrade gracefully.
- Article ranking and editorial decisions remain server-side.
- The application displays summaries in read mode; the original publisher page is
  available through web mode or the browser action.
- Narrative speech is produced on-device.

Some native capabilities require a custom build and cannot be fully exercised in
Expo Go, including native social login and some menu integrations.

## Database

PostgreSQL is hosted by Supabase and accessed through `psycopg2`.

Core tables include:

- `topics`
- `news_sources`
- `articles`
- `daily_reports`
- `generation_runs`
- `briefing_narratives`
- `narrative_audio_variants`
- `editorial_perspectives`
- `editorial_watch_next`
- `user_devices`
- `product_events`
- `profiles`
- `user_preferences`
- `saved_articles`
- `entitlements`

Important invariants:

- An article with `report_id IS NULL` is an unselected candidate.
- Selected articles reference a `daily_reports` row.
- `content_hash` enforces ingestion deduplication.
- Saved articles keep an independent content copy and survive archive cleanup.
- Read-time intelligence layers do not write new pipeline records.

Migrations are stored in `backend/migrations/`. They are designed to be
idempotent and are applied through the Supabase SQL editor. Any schema change
requires a new numbered migration and a rollback assessment.

The numbering intentionally contains no `0011`. Migration `0027` is the topic
expansion migration that was previously numbered `0016`; its content was already
applied before the file was renamed.

## Authentication

Authentication uses Supabase Auth and is controlled by `ENABLE_AUTH`.

The backend verifies modern asymmetric Supabase tokens through the project's JWKS
endpoint and retains a legacy HS256 fallback for older Supabase configurations.
Algorithms are explicitly allow-listed.

Mobile social login uses native identity-token flows. Google login is verified on
iOS and its native Android flow has been exercised in an EAS development build.
Apple login requires a properly provisioned Apple Developer account and a
physical-device verification pass.

The consumer application must never contain an admin API key. Administrative
operations remain backend-only and are performed through authenticated API calls.

## Deployment

### Backend

The backend is deployed to Render from `backend/Dockerfile` and
`backend/render.yaml`.

Production requirements:

- Run exactly one backend instance while the scheduler remains in-process.
  Multiple instances would duplicate scheduled work and notifications.
- Use the Supabase transaction pooler on port `6543`.
- Keep article scraping memory limits and concurrency controls intact.
- Configure secrets in Render rather than committing them.
- Keep production CORS restricted to the intended origins.
- Use the current Render Standard resource level; the lower memory tier was
  insufficient for the complete ingestion workload with scraping enabled.

### Mobile

`mobile/eas.json` defines development, simulator, preview, and production build
profiles. Native configuration changes require a new build; a JavaScript reload
is not sufficient.

The application identifiers are:

- iOS: `com.whatsnews.app`
- Android: `com.whatsnews.app`

Privacy and terms pages are hosted at:

- `https://whatsnewsbrief.com/privacy`
- `https://whatsnewsbrief.com/terms`

## Security

The current security baseline includes:

- Row Level Security enabled on public Supabase tables.
- Direct `anon` and `authenticated` grants removed from backend-owned tables.
- Owner-scoped policies for profile access.
- Restricted execution of the profile-creation trigger function.
- Foreign-key indexes required by common access paths.
- Constant-time shared-secret checks.
- Generic client-facing server errors with detailed server-side logging.
- Explicit JWT algorithm allow-lists.
- No admin secret embedded in the mobile bundle.
- Sentry error reporting on backend and mobile.

Public Supabase storage buckets remain intentionally readable for avatar and
narrative media URLs. Changing them to private buckets would require signed URL
generation and corresponding client changes.

Do not use side-effecting admin endpoints as deployment smoke tests. The local
backend can point at production data, so an apparently harmless request can mutate
live state or trigger a real pipeline run.

## Testing

### Backend

Run:

```bash
cd backend
python3 -m unittest discover -s tests
```

The backend suite covers authentication, feed layers, admin authorization,
ingestion reliability and cleanup, notifications, archive retention, narrative
storage, translation-related routing, preferences, and other service behavior.
External database and service calls are mocked in the regular unit suite.

### Mobile

Run:

```bash
cd mobile
npx tsc --noEmit -p .
npx jest
```

The mobile suite covers pure utilities, data contracts, reading progress,
preferences, history search, achievements, speech behavior, on-device translation
state, and selected components. Native integration coverage remains partial, so
EAS builds and platform-specific smoke tests are still required.

GitHub Actions runs backend tests and mobile type-check/tests on pushes to `main`
and on pull requests targeting `main`.

## Operational Notes

- The scheduler supports multiple daily slots through
  `SCHEDULER_DAILY_TIME`.
- Per-device notification delivery uses each device's preferred local time and a
  once-per-day deduplication field.
- Report-scoped data is retained for seven days by default.
- Product analytics events are retained for 90 days by default.
- Narrative audio and avatars use Supabase Storage.
- Feed responses use an in-memory cache; use the authenticated cache-clear
  operation only when an immediate refresh is necessary.
- The article scraper intentionally prefers precision over returning navigation or
  publisher boilerplate.
- The production database and deployed services must not be used for casual
  verification of mutating operations.

## Important Design Decisions

- FastAPI is the backend framework.
- React Native with Expo is the mobile framework.
- Supabase provides PostgreSQL, authentication, and object storage.
- Direct SQL is preferred over an ORM.
- Core briefing generation always has deterministic fallback behavior.
- Bookmarks and preferences are local-first.
- Authentication is optional for core reading.
- Business and ranking logic remains in the backend.
- The feed intelligence stack computes at read time instead of adding scheduled
  write stages.
- The backend scheduler remains in-process and therefore requires a single
  deployed instance.
- Changes should be focused and incremental; avoid unrelated restructuring.
- Public API shapes should remain backward compatible unless a migration plan is
  approved.
- Every pipeline stage must fail cleanly without preventing independent later
  stages from running.
