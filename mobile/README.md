# WhatsNews Mobile

Expo + React Native frontend for WhatsNews daily topic briefings.

**This file is a quick-start only — it is not kept in sync with the app.**
For the current screen/navigation architecture, feature status, and
technical debt, see [`docs/ENGINEERING.md`](../docs/ENGINEERING.md).

## Setup

```bash
cd mobile
npm install
cp .env.example .env   # optional — defaults work for iOS Simulator
```

## Run

```bash
npx expo start
```

- Press `i` for iOS Simulator
- Press `a` for Android emulator
- Scan QR code with Expo Go on a physical device

## Backend connection

Configuration lives in `app.config.js` and reads from environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXPO_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | FastAPI backend |

(The in-app admin console and its `EXPO_PUBLIC_ADMIN_API_KEY` env var were
**removed 2026-07-06 as a security fix** — shipping an admin API key
inside the client bundle meant any user could trigger billed AI/TTS
generation or send an arbitrary push to every device. Admin actions are
now done via `curl`/Postman/the backend's own `/docs` Swagger UI. See
[`docs/ENGINEERING.md`](../docs/ENGINEERING.md)'s Security section.)

**iOS Simulator:** `127.0.0.1:8000` works out of the box.

**Physical device:** set `EXPO_PUBLIC_API_BASE_URL` to your machine's LAN IP in `.env`:

```bash
EXPO_PUBLIC_API_BASE_URL=http://192.168.x.x:8000
```

This applies to **all API calls and voice briefing audio** (`/media/audio/...`). The app resolves relative audio URLs against this base. Legacy `127.0.0.1` audio URLs in the database are rewritten to match.

Find your IP: `ipconfig getifaddr en0` (macOS)

Restart Expo after changing `.env`: `npx expo start -c`

## Backend

The FastAPI backend must be running:

```bash
cd ../backend
source venv/bin/activate
uvicorn app.main:app --reload
```
