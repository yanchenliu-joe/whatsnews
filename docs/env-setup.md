# Environment Setup

How to configure local `.env` files for WhatsNews backend and mobile app.

**Related:** [phase18-auth-redesign.md](./phase18-auth-redesign.md)

---

## Important warnings

### Never copy `.env.example` over an existing `.env`

`.env.example` is a **template** with placeholders. Copying it over your real `.env` will wipe values you already configured (database URL, OpenAI key, admin key, etc.).

**Safe workflow:**

```bash
# First-time setup only — skip if .env already exists
cp backend/.env.example backend/.env
cp mobile/.env.example mobile/.env
# Then edit .env in place; add missing keys one section at a time.
```

### Never commit secrets

- `backend/.env` and `mobile/.env` are listed in each package `.gitignore`.
- Commit only `.env.example` (placeholders, no real secrets).
- Rotate any key that was accidentally committed.

### OpenAI API key recovery

If you lose your OpenAI API key, it **cannot be retrieved** from the OpenAI dashboard. Create a new key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys), update `OPENAI_API_KEY` in `backend/.env`, and revoke the old key if you still have access to it.

Without `OPENAI_API_KEY`, the app still runs using rule-based `why_it_matters` text and skips AI refinement.

---

## Backend (`backend/.env`)

Create from template (once):

```bash
cp backend/.env.example backend/.env
```

### Required for core app + pipeline

| Variable | Where to find it | Notes |
|----------|------------------|-------|
| `DATABASE_URL` | Supabase → **Project Settings → Database → Connection string → URI** | Required for API and pipeline |

### Commonly used (optional locally)

| Variable | Where to find it | Notes |
|----------|------------------|-------|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | AI WIM refinement, narrative, TTS |
| `ADMIN_API_KEY` | Any strong random string, e.g. `openssl rand -hex 32` | Protects `/admin/*`; must match mobile |
| `ENABLE_SCHEDULER` | Set `true` or `false` | In-process daily pipeline scheduler |

See `backend/.env.example` for scheduler, Google Sheets, voice, RSS, and editorial flags.

### Authentication (Phase 18) — optional, default off

| Variable | Default | Required when |
|----------|---------|---------------|
| `ENABLE_AUTH` | `false` | Always set explicitly in prod |
| `SUPABASE_URL` | — | `ENABLE_AUTH=true` (Phase 18.2+) |
| `SUPABASE_JWT_SECRET` | — | `ENABLE_AUTH=true` (Phase 18.2+) |

When `ENABLE_AUTH=false` (default), **no Supabase auth vars are required**. Briefing, history, narrative, and voice APIs stay public.

#### Where to find Supabase values (backend)

| Value | Location in Supabase Dashboard |
|-------|--------------------------------|
| **Project URL** | **Project Settings → API → Project URL** → use for `SUPABASE_URL` |
| **Legacy JWT Secret** | **Project Settings → API → JWT Settings → Legacy JWT Secret** → use for `SUPABASE_JWT_SECRET` (Phase 18.2+ only) |

The JWT secret verifies `Authorization: Bearer` tokens from Supabase Auth on `GET /auth/me` (Phase 18.2).

**Rollback:** set `ENABLE_AUTH=false` in `backend/.env` and restart the server. `/auth/me` returns `503 Auth disabled`; public APIs unchanged.

#### Backend `/auth/me` (Phase 18.2)

| `ENABLE_AUTH` | Request | Response |
|---------------|---------|----------|
| `false` | any | `503` — `Auth disabled` |
| `true` | no `Authorization` header | `401` — missing header |
| `true` | invalid/expired Bearer token | `401` — invalid or expired token |
| `true` | valid Supabase access token | `200` — profile JSON |

Profile response shape:

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": null,
  "avatar_url": null
}
```

Requires migration `backend/migrations/0012_phase_18_1_user_profiles.sql` (run once in Supabase SQL editor or via `psql`).

#### Token testing steps

1. Enable backend auth in **your** `backend/.env` (never commit):
   ```bash
   ENABLE_AUTH=true
   SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
   SUPABASE_JWT_SECRET=your-legacy-jwt-secret
   ```
2. Run migration 0012 if not already applied.
3. Restart backend: `uvicorn app.main:app --reload`
4. Sign in on mobile (18.1D) or via Supabase Auth API to obtain an **access_token**.
5. Call `/auth/me`:
   ```bash
   curl -s http://localhost:8000/auth/me \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN" | jq .
   ```
6. Confirm public APIs still work without a token:
   ```bash
   curl -s "http://localhost:8000/daily-report?topic=world" | jq '.date'
   curl -s http://localhost:8000/auth/me | jq .   # 401 when auth enabled
   curl -s http://localhost:8000/auth/me | jq .   # 503 when auth disabled
   ```

Never log or paste access tokens into commits or screenshots.

#### Bookmark sync (Phase 18.3)

Authenticated endpoints (require `ENABLE_AUTH=true` + Bearer token):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/me/saved-articles` | List user's saved articles (newest first) |
| `POST` | `/me/saved-articles` | Upsert save by `article_url` (idempotent) |
| `DELETE` | `/me/saved-articles/{identifier}` | Delete by URL (encoded) or numeric saved row id |

When `ENABLE_AUTH=false`, these return `503 Auth disabled`.

Requires migration `backend/migrations/0014_phase_18_3_saved_articles.sql`.

Mobile merges local AsyncStorage bookmarks with remote on sign-in; local bookmarks always work when signed out or auth disabled.

#### User preferences (Phase 18.4)

Authenticated endpoints (require `ENABLE_AUTH=true` + Bearer token):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/me/preferences` | Read user preferences JSON |
| `PATCH` | `/me/preferences` | Shallow-merge allowed preference keys |

Allowed keys: `default_topic`, `preferred_voice_profile` (`female`|`male`), `push_notifications_enabled` (boolean).

When `ENABLE_AUTH=false`, these return `503 Auth disabled`.

Requires migration `backend/migrations/0015_phase_18_4_user_preferences.sql`.

Mobile stores preferences locally in AsyncStorage; syncs to backend when signed in.

---

## Mobile (`mobile/.env`)

Create from template (once):

```bash
cp mobile/.env.example mobile/.env
```

Restart Expo after changes: `npx expo start -c`

### Required for normal app use (Phase 17.5+)

| Variable | Notes |
|----------|-------|
| `EXPO_PUBLIC_API_BASE_URL` | Backend URL. Simulator: `http://127.0.0.1:8000`. Physical device: your machine LAN IP |
| `EXPO_PUBLIC_ADMIN_API_KEY` | Must match `ADMIN_API_KEY` in backend for admin console |

### Authentication (Phase 18) — optional, default off

| Variable | Default | Required when |
|----------|---------|---------------|
| `EXPO_PUBLIC_ENABLE_AUTH` | `false` | — |
| `EXPO_PUBLIC_SUPABASE_URL` | — | `EXPO_PUBLIC_ENABLE_AUTH=true` (Phase 18.1D+) |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | — | `EXPO_PUBLIC_ENABLE_AUTH=true` (Phase 18.1D+) |

When `EXPO_PUBLIC_ENABLE_AUTH=false` (default), **no Supabase vars are required**. The app boots like Phase 17.5 with local bookmarks only.

#### Where to find Supabase values (mobile)

| Value | Location in Supabase Dashboard |
|-------|--------------------------------|
| **Project URL** | **Project Settings → API → Project URL** → `EXPO_PUBLIC_SUPABASE_URL` |
| **Publishable / anon key** | **Project Settings → API → Project API keys** → **anon** `public` or **publishable** key → `EXPO_PUBLIC_SUPABASE_ANON_KEY` |

Use the **anon** (publishable) key on mobile — never the **service_role** secret.

---

## Gitignore

Both local env files are ignored by git:

- `backend/.gitignore` → `.env`
- `mobile/.gitignore` → `.env`, `.env*.local`

---

## Quick verification

**Backend (auth off — default):**

```bash
cd backend
# ENABLE_AUTH unset or false — server starts without SUPABASE_* vars
uvicorn app.main:app --reload
```

**Mobile (auth off — default):**

```bash
cd mobile
npx expo start
# No EXPO_PUBLIC_SUPABASE_* required
```

**Phase 18 auth (later subphases only):**

1. Enable flags in **your** `.env` files (not `.env.example`).
2. Set Supabase URL + keys as above.
3. Follow [phase18-auth-redesign.md](./phase18-auth-redesign.md) subphase checklist.

---

## Config helpers (code)

| Package | File | Purpose |
|---------|------|---------|
| Backend | `backend/app/auth/config.py` | `auth_enabled()` reads `ENABLE_AUTH`, default `false` |
| Backend | `backend/app/auth/jwt.py` | Verify Supabase Bearer JWT (Phase 18.2) |
| Backend | `backend/app/auth/routes.py` | `GET /auth/me` (Phase 18.2) |
| Mobile | `mobile/src/config/auth.ts` | `isAuthEnabled()`, `getSupabaseConfig()` |
| Mobile | `mobile/src/lib/supabase/client.ts` | Lazy Supabase singleton (Phase 18.1B) |
| Mobile | `mobile/src/context/AuthContext.tsx` | Session + email auth (Phase 18.1C–18.1D) |

These helpers do not change App boot flow until Phase 18.1C.

**Backend auth rollback:** `ENABLE_AUTH=false` → `/auth/me` returns `503 Auth disabled`.

### Supabase client behavior (Phase 18.1B)

Module: `mobile/src/lib/supabase/client.ts`

| Function | Auth off | Auth on, missing URL/key | Auth on, configured |
|----------|----------|--------------------------|---------------------|
| `getSupabaseStatus()` | `{ state: "disabled" }` | `{ state: "missing_config" }` | `{ state: "ready" }` |
| `getSupabaseClientOrNull()` | `null` | `null` | singleton client |
| `getSupabaseClient()` | throws `AuthDisabledError` | throws `MissingSupabaseConfigError` | singleton client |

- Client is created **lazily** on first successful access — never at import time.
- When auth is disabled, **no Supabase env vars are read or required**.
- Session persistence uses `@react-native-async-storage/async-storage` when a client exists.
- `detectSessionInUrl: false` (no deep linking).

**Isolated verification (does not affect app boot):**

```bash
cd mobile
npm run verify:supabase
npx tsc --noEmit
```
