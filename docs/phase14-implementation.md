# Phase 14 — Voice Narrative Implementation Notes

**Status:** Phase 14.1–14.5 complete   (backend audio + mobile playback + History integration)  
**Last updated:** 2026-06-26

Design: [phase14-voice-narrative-design.md](./phase14-voice-narrative-design.md)

## Pipeline

```
Briefing data → Narrative script → TTS audio → (mobile playback in 14.3)
```

Audio is generated from persisted `script_text` only — never from raw article bodies.

## Phase 14.1 — Narrative script

### Database

- Migration: `backend/migrations/0006_phase_14_1_briefing_narratives.sql`
- Table: `briefing_narratives` (`scope=daily`, nullable `topic_id`, versioned)

### Backend modules

| Module | Role |
|--------|------|
| `app/narrative/loader.py` | Load ranked articles via `briefing_repository` |
| `app/narrative/generator.py` | Rule-based six-section script |
| `app/narrative/refine.py` | Optional OpenAI polish |
| `app/narrative/quality.py` | Pre-ready validation |
| `app/narrative/repository.py` | DB persist/load |
| `app/narrative/service.py` | Orchestration |
| `app/narrative/routes.py` | HTTP endpoints |

### API

| Endpoint | Description |
|----------|-------------|
| `GET /narratives/latest` | Latest ready daily narrative |
| `GET /narratives/daily/{report_date}` | Ready narrative for date |
| `POST /admin/narratives/generate?date=&regenerate=` | Admin generate script |

Public endpoints return **404** until `status=ready`.

## Phase 14.2 — TTS + audio storage

### Database

- Migration: `backend/migrations/0007_phase_14_2_narrative_audio.sql`
- Audio metadata columns on `briefing_narratives`:
  - `audio_status`, `audio_url`, `audio_storage_path`, `audio_duration_seconds`
  - `audio_voice`, `audio_model`, `audio_generated_at`, `audio_error_message`

### Backend modules

| Module | Role |
|--------|------|
| `app/narrative/audio_config.py` | Env defaults |
| `app/narrative/audio_prepare.py` | Strip markdown/URLs, chunk for TTS limits |
| `app/narrative/audio_tts.py` | OpenAI TTS synthesis |
| `app/narrative/audio_storage.py` | Local file paths + public URLs |
| `app/narrative/audio_quality.py` | Non-empty file / duration checks |
| `app/narrative/audio_service.py` | Orchestration |

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | Required for TTS (same key as WIM refinement) |
| `VOICE_TTS_PROVIDER` | `openai` | TTS provider (only `openai` supported) |
| `VOICE_TTS_MODEL` | `tts-1` | OpenAI TTS model |
| `VOICE_TTS_VOICE` | `nova` | OpenAI voice |
| `VOICE_AUDIO_STORAGE` | `local` | Storage backend (`local` for dev) |
| `VOICE_AUDIO_LOCAL_DIR` | `media/audio` | Relative to `backend/` |
| `VOICE_AUDIO_PUBLIC_BASE_URL` | `http://127.0.0.1:8000/media/audio` | URL prefix in API responses |
| `VOICE_TTS_MAX_CHARS` | `12000` | Cap prepared script length |
| `ENABLE_VOICE_AUDIO_GENERATION` | `false` | Scheduler TTS hook after narrative |

If `OPENAI_API_KEY` is missing, the app still runs; narrative APIs work. Admin audio generation returns **503** with a clear message.

### Storage (dev)

- Files: `backend/media/audio/daily/daily-YYYY-MM-DD-vN.mp3`
- Served at: `GET /media/audio/daily/daily-YYYY-MM-DD-vN.mp3` (FastAPI `StaticFiles`)
- API returns relative `audio.url` paths (e.g. `/media/audio/daily/...`); mobile resolves via `EXPO_PUBLIC_API_BASE_URL`

### Production storage TODO

- Move from local disk to **Supabase Storage** (or S3-compatible bucket)
- Set `VOICE_AUDIO_PUBLIC_BASE_URL` to CDN or signed-URL base
- Implement `VOICE_AUDIO_STORAGE=supabase` upload path (not in 14.2)
- Ensure ephemeral container filesystem is not used for audio in production

### API

| Endpoint | Description |
|----------|-------------|
| `POST /admin/narratives/audio/generate?date=&regenerate=` | Generate TTS for ready narrative |
| `GET /narratives/daily/{date}` | Includes `audio` metadata when present |
| `GET /narratives/latest` | Includes `audio` metadata when present |

`audio` object shape:

```json
{
  "status": "ready",
  "url": "http://127.0.0.1:8000/media/audio/daily/daily-2026-06-23-v1.mp3",
  "duration_seconds": 420,
  "generated_at": "2026-06-26T12:00:00+00:00",
  "voice": "nova",
  "model": "tts-1"
}
```

### Scheduler

After narrative in `run_scheduled_pipeline()`:

- `generate_daily_narrative(regenerate=False)` — always (14.1)
- `generate_narrative_audio(regenerate=False)` — only when `ENABLE_VOICE_AUDIO_GENERATION=true`

### Known limitations

- OpenAI TTS input limit (~4096 chars per request); long scripts are split into chunks and concatenated as MP3 bytes (works for same encoder settings; not frame-perfect).
- Duration is estimated from file size (128 kbps assumption) with word-count fallback — not frame-accurate.
- No per-topic audio; cross-topic daily scope only.
- No waveform, playlists, or mobile playback UI.

### Verification

```bash
# 1. Apply migrations
psql "$DATABASE_URL" -f backend/migrations/0006_phase_14_1_briefing_narratives.sql
psql "$DATABASE_URL" -f backend/migrations/0007_phase_14_2_narrative_audio.sql

# 2. Ensure narrative exists (use a date with publishable briefings)
curl -X POST "http://localhost:8000/admin/narratives/generate?date=2026-06-23" \
  -H "X-Admin-Key: $ADMIN_API_KEY"

# 3. Generate audio (requires OPENAI_API_KEY in .env)
curl -X POST "http://localhost:8000/admin/narratives/audio/generate?date=2026-06-23" \
  -H "X-Admin-Key: $ADMIN_API_KEY"

# 4. Read narrative with audio metadata
curl -s "http://localhost:8000/narratives/daily/2026-06-23" | jq '.audio'
curl -s "http://localhost:8000/narratives/latest" | jq '.audio.status, .audio.url'

# 5. Reuse existing audio (regenerate=false)
curl -X POST "http://localhost:8000/admin/narratives/audio/generate?date=2026-06-23" \
  -H "X-Admin-Key: $ADMIN_API_KEY" | jq '.status, .reason'

# 6. Missing API key — unset OPENAI_API_KEY, expect 503
curl -X POST "http://localhost:8000/admin/narratives/audio/generate?date=2026-06-23" \
  -H "X-Admin-Key: $ADMIN_API_KEY" | jq '.detail'

# 7. Regression
curl -s "http://localhost:8000/daily-report?topic=Technology" | jq '.date'
curl -s "http://localhost:8000/history/dates?limit=5" | jq '.count'
```

## Phase 14.3 — Mobile playback UI

### Mobile modules

| Module | Role |
|--------|------|
| `mobile/src/services/narrativeApi.ts` | `GET /narratives/latest` client |
| `mobile/src/hooks/useNarrative.ts` | Load narrative + audio metadata |
| `mobile/src/hooks/useVoicePlayback.ts` | `expo-av` play/pause |
| `mobile/src/components/VoiceBriefingCard.tsx` | Main-screen voice card |

Voice card on `BriefingScreen` (below topic chips): loading, ready, unavailable, error states.

### Verification

```bash
cd mobile && npx tsc --noEmit
# Manual: play/pause when audio ready; unavailable state when no narrative/audio
```

## Phase 14.4 — Voice polish & History integration

### Mobile

| Module | Role |
|--------|------|
| `mobile/src/utils/resolveMediaUrl.ts` | Resolve relative `/media/audio` URLs; rewrite localhost |
| `mobile/src/utils/narrativeUtils.ts` | Shared audio-ready checks |
| `mobile/src/hooks/useHistoryNarrative.ts` | `GET /narratives/daily/{date}` for History |
| `VoiceBriefingCard` | Polished UX; `today` / `history` variants |

- Today: `GET /narratives/latest`; pull-to-refresh updates voice metadata
- History: parallel narrative fetch per selected date; card above topic sections
- Date switch / navigate away stops and unloads audio
- Physical device: set `EXPO_PUBLIC_API_BASE_URL` to LAN IP (see `mobile/README.md`)

### Backend polish

- `audio.url` stored and returned as relative `/media/audio/...` when possible
- `_normalize_audio_url()` on API read for legacy absolute URLs
- Analytics: `voice_history_card_seen`, `voice_history_play_started`, `voice_history_play_failed`

## Phase 14.5 — AI platform & production readiness

### Backend modules

| Module | Role |
|--------|------|
| `app/ai/providers/base.py` | `AIProvider` interface |
| `app/ai/providers/openai_provider.py` | OpenAI chat + TTS |
| `app/ai/registry.py` | Provider selection (`AI_PROVIDER=openai`) |
| `app/ai/health.py` | In-process health monitor |
| `app/ai/usage.py` | Session usage + cost estimates |
| `app/ai/dashboard.py` | Admin dashboard aggregation |
| `app/ai/routes.py` | `/admin/ai-status`, `/admin/ai-health/simulate` |

All OpenAI calls (WIM refine, narrative refine, TTS) route through `AIProvider`.

### Admin API

```bash
curl -s "http://localhost:8000/admin/ai-status" -H "X-Admin-Key: $ADMIN_API_KEY" | jq .

# features.report_date matches GET /narratives/latest (latest READY narrative, not CURRENT_DATE)
curl -s "http://localhost:8000/narratives/latest" | jq '.report_date, .status'

# Simulate health states (verification)
curl -X POST "http://localhost:8000/admin/ai-health/simulate?scenario=invalid_api_key" \
  -H "X-Admin-Key: $ADMIN_API_KEY"
curl -X POST "http://localhost:8000/admin/ai-health/simulate?scenario=clear" \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Health statuses: `healthy`, `warning`, `degraded`, `unavailable`.

Graceful degradation: briefing/history/saved unchanged; AI failures fall back to rule-based text; voice card shows friendly unavailable states; admin errors sanitized (no API keys).

Operator Console → **AI Usage** section shows provider, health, counts, and cost estimates.

## Deferred (Phase 15+)

- Per-topic narratives
- Supabase Storage production upload
- Frame-accurate duration (e.g. mutagen)
- Waveform, playlists, background/lock-screen playback
- AI assistant layer
