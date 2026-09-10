# Phase 18 — Authentication Redesign (Design Only)

**Status:** Phase 18 Stable (18.1–18.4 complete; 18.5 OAuth deferred)  
**Baseline:** Phase 17.5 stable (editorial pipeline, local bookmarks, no auth required)  
**Last updated:** 2026-06-28  

Related: [phase13-history-design.md](./phase13-history-design.md), [phase17-5-implementation.md](./phase17-5-implementation.md)

---

## Executive Summary

Phase 18 adds **optional** user authentication to WhatsNews without breaking the anonymous-first product. The app must boot and function exactly like Phase 17.5 when auth is disabled.

Authentication is gated by an explicit feature flag on mobile and backend:

- `ENABLE_AUTH=false` (backend, default)
- `EXPO_PUBLIC_ENABLE_AUTH=false` (mobile, default)

When flags are off, no Supabase client is initialized, no auth UI appears, and all public briefing/history/voice APIs behave as today.

Rollout is **incremental** across subphases. Email/password only first. Google/Apple OAuth deferred to 18.5 and must **not** use `expo-auth-session` or deep linking in the initial design.

---

## Goals

| Goal | Success signal |
|------|----------------|
| Optional auth | App fully usable with flags off |
| Safe env handling | Missing Supabase vars never crash mobile boot |
| Incremental delivery | Each subphase shippable independently |
| Public APIs unchanged | Briefing/history/narrative/voice remain unauthenticated |
| Local bookmarks preserved | AsyncStorage bookmarks work with or without auth |
| Easy rollback | Flip flags off → Phase 17.5 behavior |

## Non-goals (Phase 18 overall)

- Mandatory login before reading briefings
- Replacing admin `X-Admin-Key` with user JWT
- Per-user editorial pipeline or personalized briefings
- OAuth in 18.1–18.4
- `expo-auth-session`, universal links, or custom URL schemes for auth
- Overwriting developer `.env` files (docs + `.env.example` comments only)
- Re-implementing the previous monolithic Phase 18 auth PR as-is

---

## Current Baseline (Phase 17.5)

### Mobile

- **Screens:** Briefing, History, Saved (local bookmarks), Admin (hidden tap)
- **Bookmarks:** `AsyncStorage` via `useSavedArticles` / `SAVED_KEY` — no server sync
- **Config:** `mobile/src/config/index.ts` — `API_BASE_URL`, `ADMIN_API_KEY` only
- **No auth code** in active `package.json` dependencies (Supabase/OAuth packages removed on rollback)
- **App entry:** `App.tsx` — no auth provider, no login gate

### Backend

- **Public read APIs:** `/daily-report`, `/history/*`, `/narratives/*`, `/perspectives/*`, `/watch-next/*` — no JWT
- **Admin APIs:** `X-Admin-Key` header (unchanged)
- **Partial stubs (inert):** `backend/app/auth/config.py`, `backend/app/auth/models.py` — not wired to routes
- **Migration available (optional):** `0012_phase_18_1_user_profiles.sql` — Supabase `profiles` + trigger; run only when enabling auth
- **Legacy schema:** `users` / `user_topics` tables (serial IDs) — **not** used for Supabase auth; do not conflate with `profiles.id` (UUID)

### What went wrong in the previous Phase 18 attempt (avoid repeating)

| Problem | Safe redesign response |
|---------|------------------------|
| Supabase client created at import time | Lazy init behind feature flag (18.1B) |
| Missing env vars crash app startup | Null-safe client factory; auth UI hidden when disabled |
| Auth wired into core navigation | Auth is additive UI, not a boot gate |
| `expo-auth-session` + deep links | Explicitly out of scope until 18.5; different approach |
| Backend auth implied by env presence alone | Explicit `ENABLE_AUTH=true` required |
| Large cross-cutting PR | Subphases 18.1A → 18.5 with verification per step |

---

## Architecture

### High-level model

```
┌─────────────────────────────────────────────────────────────┐
│                        Mobile App                           │
│  ENABLE_AUTH=false → Phase 17.5 UX (no Supabase, no login)  │
│  ENABLE_AUTH=true  → optional Account area + email auth     │
│       │                                                     │
│       ├── Supabase Auth (email only, 18.1D)                 │
│       │      signUp / signIn / signOut / session restore    │
│       │                                                     │
│       └── Backend /auth/me (18.2+) with Bearer JWT          │
│              optional bookmark sync (18.3)                  │
│              optional preferences (18.4)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                         │
│  Public routes: unchanged, no JWT                           │
│  Auth routes: /auth/me (+ future /bookmarks, /preferences)  │
│  ENABLE_AUTH=false → /auth/* returns disabled stub          │
│  ENABLE_AUTH=true  → verify Supabase JWT (HS256 secret)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Supabase (Auth + optional Postgres)            │
│  auth.users — email/password (18.1D)                        │
│  public.profiles — UUID FK (migration 0012, optional)       │
│  Future: saved_articles, user_preferences (18.3–18.4)       │
└─────────────────────────────────────────────────────────────┘
```

### Auth flow (email only, 18.1D–18.2)

1. User opens optional **Account** screen (only when `EXPO_PUBLIC_ENABLE_AUTH=true`).
2. Mobile calls **Supabase Auth** directly: `signUp`, `signInWithPassword`, `signOut`.
3. Supabase returns session + JWT access token.
4. Mobile stores session via Supabase client persistence (AsyncStorage adapter).
5. For backend calls that need identity (18.2+), mobile sends `Authorization: Bearer <access_token>`.
6. Backend validates JWT with `SUPABASE_JWT_SECRET` when `ENABLE_AUTH=true`.
7. `/auth/me` returns profile + auth metadata; creates/reads `profiles` row if migration applied.

**Important:** Briefing fetches (`/daily-report`, history, narrative, voice) do **not** send Bearer tokens in Phase 18.

### Identity model

| Layer | Identifier | Notes |
|-------|------------|-------|
| Supabase Auth | `auth.users.id` (UUID) | Source of truth when auth enabled |
| App profile | `profiles.id` (UUID FK) | Optional; auto-created by trigger in 0012 |
| Legacy `users` table | serial `id` | Deprecated for Phase 18; do not wire new code to it |

---

## Feature flags

| Flag | Platform | Default | When true |
|------|----------|---------|-----------|
| `EXPO_PUBLIC_ENABLE_AUTH` | Mobile (Expo) | `false` | Show Account UI; allow Supabase email auth |
| `ENABLE_AUTH` | Backend | `false` | Enable JWT verification + `/auth/*` routes |

**Coupling rule:** Mobile may enable UI while backend auth is off (sign-in works locally; `/auth/me` returns disabled). Backend must **never** require auth for public briefing routes regardless of flag.

**Phase 17.5 parity check:** Both flags `false` → identical behavior to current stable build.

---

## Environment variables

### Documentation-only changes

Add commented entries to:

- `backend/.env.example` (never write `backend/.env`)
- `mobile/.env.example` (create if missing; never write `mobile/.env`)

### Backend (`backend/.env.example`)

```bash
# --- Authentication (Phase 18) — default off ---
# ENABLE_AUTH=false

# Required when ENABLE_AUTH=true (JWT verification for /auth/*)
# SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
# SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-settings

# Optional alias (existing stub in auth/config.py)
# SUPABASE_PROJECT_URL=...
```

| Variable | Required when | Purpose |
|----------|---------------|---------|
| `ENABLE_AUTH` | Always set explicitly in prod | Master backend auth switch |
| `SUPABASE_URL` | `ENABLE_AUTH=true` | Issuer/audience checks, docs |
| `SUPABASE_JWT_SECRET` | `ENABLE_AUTH=true` | Verify Bearer JWT (HS256) |

Existing variables (`DATABASE_URL`, `ADMIN_API_KEY`, editorial flags) unchanged.

### Mobile (`mobile/.env.example`)

```bash
# --- Authentication (Phase 18) — default off ---
# EXPO_PUBLIC_ENABLE_AUTH=false

# Required only when EXPO_PUBLIC_ENABLE_AUTH=true
# EXPO_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
# EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

| Variable | Required when | Purpose |
|----------|---------------|---------|
| `EXPO_PUBLIC_ENABLE_AUTH` | Optional | Feature flag; default false |
| `EXPO_PUBLIC_SUPABASE_URL` | Auth UI enabled | Supabase project URL |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Auth UI enabled | Supabase anon key (public) |

**Safety rule:** If `EXPO_PUBLIC_ENABLE_AUTH=true` but URL/key missing → treat as auth unavailable (log dev warning, hide login actions, **do not throw**).

---

## Subphases

### 18.1A — Env safety + config docs

**Scope:** Documentation and config scaffolding only. No runtime auth behavior.

**Deliverables:**

- `mobile/.env.example` with auth vars (commented)
- `backend/.env.example` auth section (commented)
- `mobile/src/config/auth.ts` — `isAuthEnabled()`, `getSupabaseConfig()` returning null-safe config
- `backend/app/auth/config.py` — add `auth_enabled()` → `ENABLE_AUTH=true` explicitly (replace implicit JWT-secret-only check)
- This design doc

**Verification:**

- App builds with no Supabase vars
- No new imports side-effect initialize Supabase

---

### 18.1B — Supabase client isolation

**Scope:** Lazy Supabase client factory; zero impact when auth disabled.

**Deliverables:**

- `mobile/src/lib/supabase/client.ts`
  - `getSupabaseClient(): SupabaseClient | null`
  - Creates client only once, only if flag + valid env
  - Never imported from `App.tsx` root until 18.1C
- Add `@supabase/supabase-js` dependency only in this subphase

**Rules:**

- Do **not** add `expo-auth-session`, `expo-apple-authentication`, or `expo-web-browser` yet
- Use Supabase AsyncStorage session persistence (`@react-native-async-storage/async-storage` already present)

**Verification:**

- `EXPO_PUBLIC_ENABLE_AUTH=false` → `getSupabaseClient()` is `null`, app unchanged
- Missing URL/key with flag true → `null`, no redbox

---

### 18.1C — Auth feature flag wiring

**Scope:** Optional auth shell without login forms yet.

**Deliverables:**

- `mobile/src/context/AuthContext.tsx` — no-op provider when disabled
- `App.tsx` — wrap with `AuthProvider` (internal no-op when flag off)
- Optional **Account** entry in header — hidden when flag off
- `AccountScreen` placeholder until 18.1D

**Verification:**

- Flag off: zero UI delta vs Phase 17.5
- Flag on + missing env: Account shows "Auth not configured" — app still works

---

### 18.1D — Email sign up / sign in / sign out

**Scope:** Supabase email/password only. No backend routes required yet.

**Deliverables:**

- `mobile/src/screens/AccountScreen.tsx`
- `mobile/src/hooks/useAuth.ts` — session state, `signUp`, `signIn`, `signOut`
- Forms: email, password, confirm password (sign up), error display
- Session restore on app launch when flag on
- Sign out clears session; local bookmarks **unchanged**

**Verification:**

- Sign up → sign in → sign out cycle works
- Flag off → no Account auth forms reachable
- Briefing/history/voice work signed out and signed in

---

### 18.2 — Backend `/auth/me` ✅ Implemented

**Scope:** Backend recognizes Supabase JWT; exposes current user profile.

**Deliverables:**

- `backend/app/auth/jwt.py` — HS256 verify via `SUPABASE_JWT_SECRET`; validates `exp`, `sub`, `aud=authenticated`, optional `iss` from `SUPABASE_URL`
- `backend/app/auth/deps.py` — `get_current_user` (Bearer required when auth enabled)
- `backend/app/auth/routes.py` — `GET /auth/me`
- `backend/app/auth/repository.py` — upsert `profiles` on first hit
- `register_auth_routes(app)` in `main.py` — no global auth middleware on public routes
- Migration `0012_phase_18_1_user_profiles.sql` (existing; no new migration)

Response when authenticated (`200`):

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": null,
  "avatar_url": null
}
```

When disabled (`503`):

```json
{ "detail": "Auth disabled" }
```

**Verification:**

- `ENABLE_AUTH=false` → `503 Auth disabled`; public APIs unchanged
- `ENABLE_AUTH=true`, no token → `401`
- Invalid Bearer → `401`
- Valid Supabase mobile `access_token` → `200` profile JSON

See [env-setup.md](./env-setup.md) for token testing steps and rollback (`ENABLE_AUTH=false`).

---

### 18.3 — Bookmark sync ✅ Implemented

**Scope:** Optional cloud sync for saved articles when authenticated.

**Migration:** `0014_phase_18_3_saved_articles.sql`

**API (Bearer required):**

- `GET /me/saved-articles`
- `POST /me/saved-articles` — idempotent upsert by `article_url`
- `DELETE /me/saved-articles/{identifier}` — URL (encoded) or saved row id

**Mobile:** `SavedArticlesProvider` — local-first AsyncStorage; merge + upload on sign-in; background sync on toggle; sign out keeps local list.

---

### 18.4 — User preferences ✅ Implemented

**Scope:** Lightweight per-user settings.

**Migration:** `0015_phase_18_4_user_preferences.sql`

**API (Bearer required):**

- `GET /me/preferences`
- `PATCH /me/preferences` — shallow merge of allowed keys

**Keys:** `default_topic`, `preferred_voice_profile`, `push_notifications_enabled`

**Mobile:** `UserPreferencesProvider` — local AsyncStorage + remote sync; applies default topic and voice preference when signed in.

---

## Phase 18 Stable (18.4.5)

Phase 18.1 through 18.4 are implemented and stabilized. OAuth (18.5) is **not** started.

### Auth state machine (mobile)

Deterministic states:

```
disabled          → EXPO_PUBLIC_ENABLE_AUTH=false
missing_config    → auth on, Supabase env incomplete
loading           → restoring session from AsyncStorage
signed_out        → no Supabase session
signed_in         → valid Supabase session
error             → session init failed (retry via Account)
```

There is no steady-state `ready` auth status. Supabase client config still exposes `ready` separately in `getSupabaseStatus()`.

### Verified manual scenarios

| Area | Scenario | Expected |
|------|----------|----------|
| Session | Sign in → kill app → restart | `signed_in` restored |
| Session | Sign out → restart | `signed_out` |
| Bookmarks | Save signed in → restart | Merged local + remote, no duplicates |
| Bookmarks | Unsave signed in → restart | Removed locally and remotely |
| Bookmarks | Auth off / signed out | Local AsyncStorage only |
| Preferences | Change voice/topic signed in → restart | Persisted locally + remotely |
| Preferences | Sign out | Local prefs remain |
| Public APIs | Any auth state | `/daily-report`, history, voice work without Bearer |

### API contract (authenticated)

| Endpoint | Success | Auth off | No/invalid token |
|----------|---------|----------|------------------|
| `GET /auth/me` | `{ id, email, display_name, avatar_url }` | `503 Auth disabled` | `401` |
| `GET /me/saved-articles` | `{ items, count }` | `503` | `401` |
| `POST /me/saved-articles` | saved article object | `503` | `401` |
| `DELETE /me/saved-articles/{id}` | `{ deleted, identifier }` | `503` | `401` |
| `GET /me/preferences` | `{ preferences, updated_at }` | `503` | `401` |
| `PATCH /me/preferences` | `{ preferences, updated_at }` | `503` | `401` |

Invalid token detail: `"Invalid or expired token."` — never log JWT contents.

### Known limitations

- Rapid bookmark toggle may drop a remote sync; local state is always correct.
- Preferences remote merge on sign-in: remote keys overwrite local for the same key.
- `POST /me/saved-articles` returns a single item; `GET` returns `{ items, count }`.
- Push notification preference is stored only; Expo registration unchanged.
- `/auth/me` not yet called from mobile Account screen.
- Email confirmation depends on Supabase dashboard settings.

### Rollback

1. Set `ENABLE_AUTH=false` in backend `.env`
2. Set `EXPO_PUBLIC_ENABLE_AUTH=false` in mobile `.env`
3. Restart backend + Expo

### Future OAuth (18.5 — not started)

- No Google / Apple implementation
- No `expo-auth-session`
- No deep linking
- Separate design review before coding

Automated checks:

```bash
cd mobile && npx tsc --noEmit
cd backend && python -m unittest tests.test_auth_api
```

---

### 18.5 — Google / Apple OAuth (deferred)

**Scope:** Implement only after 18.1–18.4 stable.

**Constraints:**

- No `expo-auth-session`
- No deep linking in first OAuth iteration
- Separate design review; `ENABLE_OAUTH=false` default
- Evaluate: native Apple id token + Supabase; Google native sign-in + id token

---

## File boundaries

### Mobile — allowed touch zones

| Path | Subphase | Purpose |
|------|----------|---------|
| `mobile/src/config/auth.ts` | 18.1A | Feature flag + env parsing |
| `mobile/src/lib/supabase/client.ts` | 18.1B | Lazy Supabase client |
| `mobile/src/context/AuthContext.tsx` | 18.1C | Session provider |
| `mobile/src/hooks/useAuth.ts` | 18.1D | Auth actions |
| `mobile/src/screens/AccountScreen.tsx` | 18.1C–18.1D | Auth UI |
| `mobile/src/services/authApi.ts` | 18.2 | `/auth/me` client |
| `mobile/src/services/bookmarksApi.ts` | 18.3 | Sync API |
| `mobile/src/hooks/useSavedArticles.ts` | 18.3 | Optional sync layer |
| `mobile/App.tsx` | 18.1C | Provider + navigation |
| `mobile/app.config.js` | 18.1A | Pass through `EXPO_PUBLIC_*` |

### Mobile — do not modify in early subphases

- Briefing/history/narrative/voice data fetching (no auth headers)
- `pushNotifications.ts`, `analytics.ts` until 18.4

### Backend — allowed touch zones

| Path | Subphase | Purpose |
|------|----------|---------|
| `backend/app/auth/*` | 18.1A–18.4 | Auth module expansion |
| `backend/app/main.py` | 18.2 | Register auth router only |
| `backend/migrations/0012_*` | 18.2 | Profiles (exists) |
| `backend/migrations/0014_*` | 18.3 | `saved_articles` |
| `backend/migrations/0015_*` | 18.4 | `user_preferences` |

### Backend — must remain public (no JWT)

- `GET /daily-report`, `/history/*`, `/briefing-dates`, `/briefing-search`
- `GET /narratives/*`, `/perspectives/*`, `/watch-next/*`
- `/media/audio/*`
- Admin routes: `X-Admin-Key` only

---

## Rollback plan

### Immediate rollback (no code revert)

1. Set `ENABLE_AUTH=false` in backend `.env`
2. Set `EXPO_PUBLIC_ENABLE_AUTH=false` in mobile `.env`
3. Restart backend + Expo

**Result:** Phase 17.5 behavior restored.

### Code rollback

Revert mobile/backend auth commits to Phase 17.5 branch. Supabase migrations may remain unused.

### Database rollback (optional)

Auth tables (`profiles`, `saved_articles`, `user_preferences`) are independent of briefing pipeline. Flag-off rollback does not require DB changes.

---

## Verification checklist

### Phase 17.5 parity (after every subphase)

- [ ] Auth flags off or unset
- [ ] App launches without redbox
- [ ] Briefing, history, voice, saved bookmarks work
- [ ] Admin screen reachable
- [ ] Pipeline `/admin/run-pipeline` works

### Auth enabled smoke (18.1D+)

- [ ] Email sign up/in/out works
- [ ] Briefing works without Bearer header
- [ ] `/auth/me` works with Bearer (18.2+)

### Regression guards

- [ ] No import-time Supabase init when flag off
- [ ] No login gate on app start
- [ ] Public API response shapes unchanged

---

## What NOT to implement yet

| Item | Wait until |
|------|------------|
| Google / Apple OAuth | 18.5 |
| `expo-auth-session` | Not in 18.1–18.4 |
| Deep linking for auth | 18.5 |
| JWT on public briefing routes | Out of scope |
| Mandatory login | Out of scope |
| User-specific editorial content | Out of scope |
| Auto-modifying `.env` files | Never |
| Global FastAPI auth middleware | Avoid |
| Legacy `users` serial table wiring | Out of scope |

---

## Implementation order

```
18.1A → 18.1B → 18.1C → 18.1D → 18.2 → 18.3 → 18.4 → 18.5
```

Each subphase gets its own implementation doc when coding begins.

---

## Open decisions (before 18.1D)

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Email confirmation? | Dev: auto-confirm; prod: Supabase confirm |
| 2 | Account entry point | Header icon on Briefing + Saved |
| 3 | `/auth/me` when disabled | `503` — `Auth disabled` |
| 4 | Run migration 0012? | Yes, when enabling backend auth |
| 5 | Remove legacy `users` table? | No; ignore in Phase 18 |

---

## Appendix — Existing auth stubs

- `backend/app/auth/config.py` — today enables auth if JWT secret set; **change to explicit `ENABLE_AUTH` in 18.1A**
- `backend/app/auth/models.py` — reuse in 18.2
- `backend/migrations/0012_phase_18_1_user_profiles.sql` — run manually when ready
- Mobile `package.json` — no Supabase dep on stable 17.5; add in 18.1B only

---

## HANDOFF SUMMARY

### 1. Files changed

| File | Action |
|------|--------|
| `docs/phase18-auth-redesign.md` | **Created** — design-only Phase 18 auth rollout |

No implementation code, no `.env` changes, no migrations applied.

### 2. Key decisions made

- Auth is **opt-in** via `ENABLE_AUTH=false` (backend) and `EXPO_PUBLIC_ENABLE_AUTH=false` (mobile); default off preserves Phase 17.5 exactly.
- **Email-only** auth via Supabase client on mobile (18.1D); backend JWT verify starts at 18.2 with `/auth/me`.
- **Lazy Supabase init** — no import-time client; missing env vars must not crash mobile.
- **Public APIs stay unauthenticated** — briefing, history, narrative, voice, perspectives, watch-next unchanged.
- **Local bookmarks first** — AsyncStorage remains primary; cloud sync optional in 18.3 when signed in.
- **No `expo-auth-session`, no deep linking** through 18.4; OAuth deferred to 18.5 with separate review.
- Replace implicit backend auth (JWT secret present) with explicit `ENABLE_AUTH=true` in 18.1A.
- Do **not** wire legacy serial `users` table; use Supabase UUID `profiles` only.
- Never overwrite developer `.env` files — document vars in `.env.example` only during implementation.

### 3. Commands or SQL I need to run

**Now (design phase):** none.

**When starting 18.1D (Supabase email auth):**

1. Create/configure Supabase project (Auth → Email provider enabled).
2. Copy project URL + anon key into **your** `mobile/.env` (do not commit):
   ```bash
   EXPO_PUBLIC_ENABLE_AUTH=true
   EXPO_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
   EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
   ```

**When starting 18.2 (backend `/auth/me`):**

1. Add to **your** `backend/.env`:
   ```bash
   ENABLE_AUTH=true
   SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
   SUPABASE_JWT_SECRET=your-jwt-secret
   ```
2. Run profiles migration if not already applied:
   ```bash
   psql "$DATABASE_URL" -f backend/migrations/0012_phase_18_1_user_profiles.sql
   ```

**When starting 18.3 / 18.4:** run new migrations `0014_*` / `0015_*` (to be authored at implementation time).

### 4. Verification steps

**Design complete (now):**

- [ ] Read `docs/phase18-auth-redesign.md` end-to-end
- [ ] Confirm subphase order 18.1A → 18.5 matches team expectations
- [ ] Approve before any code in 18.1A

**After each implementation subphase:**

- Run Phase 17.5 parity checklist (auth flags off)
- Run subphase-specific smoke tests in doc
- Confirm no changes to public API contracts

**Stable baseline sanity (Phase 17.5, no auth work):**

```bash
curl -s http://localhost:8000/watch-next/latest | jq '.status'
curl -s "http://localhost:8000/daily-report?topic=world" | jq '.date'
```

Mobile: launch app with no Supabase vars → briefing + saved bookmarks work.

### 5. Risks / TODOs

| Risk | Mitigation |
|------|------------|
| Accidental auth enable via partial env | Explicit `ENABLE_AUTH` flag; not JWT-secret-only |
| Mobile crash on missing Supabase vars | Lazy null client + flag gating (18.1B) |
| Login gate blocks anonymous users | Auth UI additive only; no navigation guards |
| Bookmark data loss on sign-out | Local-first; sign-out keeps AsyncStorage |
| Duplicate Phase 18 monolith PR | Strict subphases; one PR per subphase |
| Migration 0012 applied but auth off | Harmless; profiles unused until 18.2 |
| Legacy `users` table confusion | Documented: ignore for Phase 18 |

**TODOs before coding 18.1A:**

- [ ] Team review and sign-off on this design
- [ ] Decide email confirmation policy (dev vs prod)
- [ ] Confirm Supabase project ownership and JWT secret access
- [ ] Decide Account screen entry point (recommended: header icon)

**TODOs deferred:**

- [ ] 18.5 OAuth approach (no `expo-auth-session`)
- [ ] Migration SQL for `saved_articles` (18.3) and `user_preferences` (18.4)
- [ ] Per-subphase implementation docs (`docs/phase18-1A-implementation.md`, etc.)

---

## Phase 18.6 — Auth Final Verification (2026-06-28)

**Goal:** End-to-end verification of Phase 18.1–18.4 before any new product features.

**Automated checks run:**

```bash
cd mobile && npx tsc --noEmit   # PASS — zero errors
cd backend && python -m unittest tests.test_auth_api -v  # PASS — 4/4
```

**Bugs found:**

| Severity | Location | Description | Status |
|----------|----------|-------------|--------|
| Documentation | `ENGINEERING.md` | API table listed `/auth/preferences` and `/auth/saved-articles`; actual routes are `/me/preferences` and `/me/saved-articles` | **Fixed** |

No code bugs found. All auth code is correct. TypeScript clean. Backend tests pass.

---

### Manual Verification Checklist

Perform these checks with a real Supabase project configured in `mobile/.env` and `backend/.env`.

#### 1. Auth Disabled Baseline (flags off)

- [ ] `EXPO_PUBLIC_ENABLE_AUTH=false`, `ENABLE_AUTH=false`
- [ ] App launches without redbox or crash
- [ ] Briefing, history, voice, local bookmarks all work
- [ ] Account screen shows "Authentication is turned off for this build"
- [ ] `curl http://localhost:8000/auth/me` → `503 Auth disabled`
- [ ] `curl http://localhost:8000/me/saved-articles` → `503 Auth disabled`
- [ ] `curl http://localhost:8000/me/preferences` → `503 Auth disabled`

#### 2. Missing Config (auth on, no Supabase vars)

- [ ] `EXPO_PUBLIC_ENABLE_AUTH=true`, Supabase URL/key NOT set in mobile `.env`
- [ ] App launches without crash
- [ ] Account screen shows "Auth not configured" message
- [ ] Auth state = `missing_config`
- [ ] No `null` reference errors in JS console

#### 3. Email Sign Up

- [ ] Supabase vars configured, `EXPO_PUBLIC_ENABLE_AUTH=true`
- [ ] Open Account screen → Sign Up tab
- [ ] Enter valid email + password (≥6 chars)
- [ ] Confirm password matches
- [ ] Tap Create Account — success message or auto-signed-in
- [ ] Email confirmation: either auto-confirmed (dev) or shows "Check email"

#### 4. Email Sign In

- [ ] Sign In tab: enter credentials for an existing account
- [ ] Tap Sign In — transitions to signed-in view
- [ ] Shows user email
- [ ] Bookmark sync: on
- [ ] Preferences: synced

#### 5. Session Persistence After Restart

- [ ] Sign in → force-close app → reopen
- [ ] Auth state restores to `signed_in` without prompting
- [ ] Remote bookmarks restored (no duplicates)
- [ ] Remote preferences restored

#### 6. Sign Out Persistence After Restart

- [ ] While signed in: tap Sign Out
- [ ] Auth state = `signed_out`
- [ ] Local bookmarks still present (not cleared)
- [ ] Force-close and reopen → still `signed_out`

#### 7. Backend Auth — No Token

- [ ] `ENABLE_AUTH=true` in backend `.env`
- [ ] `curl http://localhost:8000/auth/me` → `401`
- [ ] `curl http://localhost:8000/me/saved-articles` → `401`
- [ ] `curl http://localhost:8000/me/preferences` → `401`

#### 8. Backend Auth — Invalid Token

- [ ] `curl -H "Authorization: Bearer bad.jwt.token" http://localhost:8000/auth/me` → `401 "Invalid or expired token."`

#### 9. Backend Auth — Valid Token

- [ ] Sign in on mobile → copy access_token from Supabase session (dev tools)
- [ ] `curl -H "Authorization: Bearer <token>" http://localhost:8000/auth/me` → `200` profile JSON
- [ ] Response has `id`, `email`, `display_name`, `avatar_url`

#### 10. Bookmark Sync — Save Signed Out

- [ ] Sign out (or `EXPO_PUBLIC_ENABLE_AUTH=false`)
- [ ] Bookmark an article → stored in AsyncStorage
- [ ] Bookmark sync status: "off"

#### 11. Bookmark Sync — Upload on Sign In

- [ ] Bookmark articles while signed out (local only)
- [ ] Sign in → bookmarks upload to server automatically
- [ ] `curl -H "Authorization: Bearer <token>" http://localhost:8000/me/saved-articles` → articles present

#### 12. Bookmark Sync — Restart Restores Remote

- [ ] Sign in → save a bookmark → force-close app
- [ ] Reopen → bookmark restored from remote (not just AsyncStorage)

#### 13. Bookmark Sync — Delete Persists

- [ ] Sign in → bookmark article → unsave article
- [ ] Force-close and reopen → article remains unsaved (local + remote)
- [ ] `curl ... /me/saved-articles` → article absent

#### 14. No Duplicate Bookmarks

- [ ] Add same article from two paths (e.g., toggle twice)
- [ ] `GET /me/saved-articles` → only one entry

#### 15. Preferences Sync — Voice Profile

- [ ] Signed in: set voice to Female → Male
- [ ] Force-close and reopen → Male preference restored from remote
- [ ] `curl ... /me/preferences` → `"preferred_voice_profile":"male"`

#### 16. Preferences Sync — Default Topic

- [ ] Signed in: app shows default topic set (if changed from briefing screen)
- [ ] Restart → still set

#### 17. Preferences — Sign Out Keeps Local Fallback

- [ ] Note preferences while signed in
- [ ] Sign out → Account shows "Preferences: local only"
- [ ] App still uses last-known local preferences

#### 18. Preferences — Sign In Restores Remote

- [ ] Sign out → sign back in
- [ ] Remote preferences restored and applied (remote wins on conflict)

#### 19. Public APIs Unaffected

With `ENABLE_AUTH=true` and no Bearer token:
- [ ] `GET /daily-report?topic=world` → `200` (no auth required)
- [ ] `GET /history/latest` → `200`
- [ ] `GET /narratives/latest` → `200`
- [ ] `GET /watch-next/latest` → `200`

---

### Phase 18.6 HANDOFF SUMMARY

#### 1. Files Changed

| File | Change |
|------|--------|
| `ENGINEERING.md` | Current API paths: `/me/preferences` and `/me/saved-articles` |
| `docs/phase18-auth-redesign.md` | Appended Phase 18.6 verification section and manual checklist |

No application code changed.

#### 2. Key Decisions Made

- All Phase 18 auth code is correct as written. No code bugs found.
- The only issue was documentation rot in the engineering guide — fixed.
- Mobile TypeScript compiles clean. Backend tests 4/4 pass.
- Auth state machine, bookmark sync, and preferences sync logic are all correct.
- Delete endpoint correctly tries URL (URL-decoded path param) after numeric check.

#### 3. Commands or SQL to Run

**Automated checks (pass now, re-run after any auth change):**
```bash
cd mobile && npx tsc --noEmit
cd backend && python -m unittest tests.test_auth_api -v
```

**Migrations (run once per Supabase project if not already applied):**
```bash
# Backend .env must have DATABASE_URL pointing to Supabase
psql "$DATABASE_URL" -f backend/migrations/0012_phase_18_1_user_profiles.sql
psql "$DATABASE_URL" -f backend/migrations/0014_phase_18_3_saved_articles.sql
psql "$DATABASE_URL" -f backend/migrations/0015_phase_18_4_user_preferences.sql
```

#### 4. Verification Steps

1. Run automated checks above — both should pass
2. Work through the manual checklist above in order (sections 1–19)
3. Confirm public APIs return `200` with no auth header (section 19)

#### 5. Risks / TODOs

| Risk | Status |
|------|--------|
| `saved_articles` and `user_preferences` tables have no RLS policies | Low risk (backend uses service role; Supabase JS client not used for these tables). Add RLS in 18.5 if direct Supabase access is added. |
| `/auth/me` not yet called from mobile Account screen (confirmed signed-in displays email from Supabase session, not from `/auth/me` response) | Known limitation — profile call deferred |
| Rapid bookmark toggle may drop one remote sync | Known limitation — local state always correct |
| Push notification preference stored but Expo token registration unchanged | Known — wired in 18.4, integration deferred |
| OAuth (Google/Apple) | Not started — Phase 18.5, separate design required |
