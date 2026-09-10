# Google Play Console listing draft

Draft copy + submission answers for the Google Play Console listing. Edit
freely — grounded in what the app actually does today (free, no
subscriptions, 20 topics, on-device voice, 12-language UI) and in
`docs/legal/privacy-policy.md`. The iOS equivalent is
`docs/legal/app-store-listing.md`; where the two stores ask for the same
thing the copy is intentionally kept consistent.

Package name: `com.whatsnews.app` · current `versionCode: 1` (app.json).

---

## Store listing

### App name (30 char max)
WhatsNews: Daily Briefing

### Short description (80 char max)
One daily news briefing across 20 topics — curated, concise, read aloud.
<!-- 76 chars incl. spaces — under the 80 limit -->

### Full description (4000 char max)

WhatsNews delivers one focused news briefing a day — not an endless feed.
Every morning, we scan hundreds of sources across 20 topics, pick the
stories that matter, and explain why each one matters to you.

FOCUSED, NOT ENDLESS
A single daily briefing per topic, not a bottomless scroll. Read it in
minutes, then get back to your day.

WHY IT MATTERS
Every story comes with a short "why it matters" note — the context you
need, without digging for it yourself.

LISTEN, DON'T JUST READ
Prefer audio? WhatsNews reads your briefing aloud right on your device —
perfect for a commute or a morning routine.

BROWSE THE ARCHIVE
Missed a day? Recent briefings are saved and searchable so you can catch
up on what you missed.

BUILD YOUR STREAK
Track your daily reading streak, unlock milestones, and see your reading
history on a calendar.

YOUR TOPICS, YOUR LANGUAGE
Choose which of 20 topics you follow. Read the app itself in any of 12
languages, with full right-to-left support for Arabic and Urdu.

FREE, NO CATCH
WhatsNews is completely free. No subscription, no ads, no paywalled
articles.

An account is optional — you can use WhatsNews fully without signing in.
Sign in only if you want your saved articles and preferences to follow
you across devices.

### App category
- **Category:** News & Magazines
- **Tags:** up to 5 in Play Console — suggest: News, Daily briefing,
  News digest, Current events, Text to speech

### Contact details
- **Email (required):** contact@whatsnewsbrief.com
- **Website (optional):** https://whatsnewsbrief.com
- **Phone (optional):** leave blank

### Privacy Policy URL (required)
https://whatsnewsbrief.com/privacy

> Must be live and publicly reachable before Google will let you roll out
> to production. The content lives at `docs/legal/privacy-policy.md` —
> publish it at that exact URL.

---

## Graphics assets

| Asset | Spec | Status |
|---|---|---|
| App icon | 512×512 PNG, 32-bit | Done — `docs/store-assets/play-store-icon-512.png` (derived from the real "W" mark, replacing the old Expo placeholder) |
| Feature graphic | 1024×500 PNG/JPG | Done — `docs/store-assets/feature-graphic-1024x500.png` |
| Phone screenshots | min 2, max 8; 16:9 or 9:16, each side 320–3840px | Done — `docs/store-assets/phone-screenshots/` (5 images, 1080×2160, real production data from the `whatsnews_playstore_test` emulator) |
| 7-inch / 10-inch tablet screenshots | **Required by Play Console's listing form** (marked `*`), same spec as phone (16:9 or 9:16, each side 320–3840px, ≤8MB) | Done — `docs/store-assets/tablet-screenshots/` (the same 5 phone-screenshot files, copied as-is). This app has no tablet-specific layout (phone-only, same as iOS's `supportsTablet: false`) — Play doesn't validate that tablet-slot images actually render tablet UI, only that they meet the size/aspect spec, and the phone screenshots already satisfy it. If you'd rather not carry fake "tablet" screenshots at all, the cleaner long-term fix is to restrict the app to phone form factor in Play Console (Device catalog / Advanced settings) — that removes the tablet-screenshot requirement instead of working around it. |
| Chromebook / Android XR screenshots | Optional (no `*`) | Not provided — no Chromebook/XR-specific captures exist, and the form doesn't require them. Skip. |

**Screenshots captured** (`docs/store-assets/phone-screenshots/`):
`1-briefing.png` (main feed + Morning Brief voice card),
`2-article-why-it-matters.png` (open article), `3-archive.png` (Archive/
date browsing), `4-streak.png` (Streak tab — calendar, milestones,
badges), `5-account.png` (Account/language screen). Real signed-in
account, real backend data — not a mockup. Note: the Streak screenshot
shows "0 days" since the test account hadn't read 3 articles that day
yet; swap it for a screenshot from an account with an active streak if
you want the marketing image to show progress, otherwise it's fine as-is
(a legitimate real render either way). Cropped to 1080×2160 from the
emulator's native 1080×2400 to satisfy Play's 2:1 max aspect-ratio limit
(the raw capture was 2.22:1, just over the cap). `5-account.png` was
edited (2026-07-24) to redact the real signed-in account's display name/
email ("yanchentoefl120" / `yanchentoefl120@gmail.com`) — replaced with a
generic "WhatsNews Reader" / "Signed in" pair, same font/color/position,
before this was ever uploaded anywhere public.

---

## Data safety form

Google Play's Data safety section. Grounded in `docs/legal/privacy-policy.md`.

**Does your app collect or share any of the required user data types?** Yes (collect).
**Is all of the user data collected by your app encrypted in transit?** Yes (HTTPS/TLS only).
**Do you provide a way for users to request that their data is deleted?** Yes — via contact email (account deletion on request; in-app clearing of saved articles/preferences).

### Data collected (none is "shared" — see note below)

| Data type | Collected | Linked to user | Purpose | Optional? |
|---|---|---|---|---|
| Email address | Yes | Yes | Account management, App functionality | Optional (sign-in only) |
| Name (display name) | Yes | Yes | App functionality | Optional |
| Photos (profile picture) | Yes | Yes | App functionality | Optional |
| User IDs (Supabase account id) | Yes | Yes | Account management, App functionality | Optional (sign-in only) |
| Device or other IDs (push token, anonymous install id) | Yes | No | App functionality (notifications, consistent behavior) | — |
| App interactions (analytics events) | Yes | No | Analytics | — |
| Crash logs | Yes | No | App functionality, Analytics (via Sentry) | — |
| Diagnostics (device model, OS version) | Yes | No | App functionality (via Sentry crash reports) | — |

**Data "shared" with third parties: None.** Supabase (DB/auth/photo
storage), Expo (push delivery), and Sentry (crash diagnostics) are
service providers processing data *on our behalf* — under Google's
definition this is "collection," not "sharing," so answer **No** to data
sharing.

### Explicitly NOT collected
Location (precise or approximate), Financial info / payment info (no IAP,
no subscriptions), Contacts, Calendar, SMS/Call logs, Microphone audio,
Health/fitness, Web browsing history (the in-app Web mode WebView loads
article pages but we do not record browsing history), Advertising ID /
no ad-tracking SDKs.

---

## Content rating (IARC questionnaire)

Category to select: **Reference, News, or Educational** (news app).

Expected answers — almost all "No":
- Violence, sexual content, profanity, controlled substances, gambling,
  crude humor, user-to-user interaction, sharing user location: **No**
  (WhatsNews shows curated news summaries; it has no user-generated
  content visible to others and no social features).
- **Does the app allow users to access the internet / open uncontrolled
  web pages?** **Yes.** Article Detail's "Web mode" toggle and "Open in
  Browser" load arbitrary third-party article URLs in a WebView. This is
  the one question that raises the rating — expect roughly **Teen /
  PEGI 12 / "everyone" with an internet-access notice** depending on the
  region's board. Answer it honestly; do not claim there is no web access.

Result: IARC issues per-region ratings automatically from these answers.

---

## Target audience & content
- **Target age group:** 13+ (not designed for or directed at children;
  see privacy policy §7). Do NOT opt into the "Designed for Families"
  program.
- **Ads:** declare **No ads** (contains no ads).

---

## App access (for review)
The core app (briefing, reading, voice, archive, streak) works fully
**without an account** — the reviewer needs no credentials. If the review
team wants to see the optional signed-in features (saved-article/
preference sync, profile photo), provide a test account or note that
Sign in with Google/Apple or email sign-up is available; no special
access is gated behind login.

---

## Submission via EAS

`eas.json` → `submit.production.android` is configured for the **internal**
track:

```
"android": {
  "serviceAccountKeyPath": "./google-play-service-account.json",
  "track": "internal",
  "releaseStatus": "completed"
}
```

Before `eas submit --platform android` will work:
1. In Google Play Console → Setup → API access (or Google Cloud Console),
   create a **service account** with the "Service Account User" role and
   grant it access in Play Console (Users & permissions → invite the
   service account email, give it "Release to testing tracks" +
   "Release apps to production" as needed).
2. Download its JSON key, save it as
   `mobile/google-play-service-account.json` (already git-ignored — never
   commit it), or point `serviceAccountKeyPath` elsewhere.
3. Build an app bundle: `eas build --platform android --profile production`
   (produces an `.aab`).
4. Submit: `eas submit --platform android --profile production` — pushes
   to the `internal` track. Change `track` to `production` (and re-run)
   when promoting to public, or promote from within Play Console.

> Note: the **very first** upload to a brand-new app on Play Console must
> often be done manually in the console UI before `eas submit` can target
> the app; since you've already published an internal-testing release,
> that first-upload step is done and `eas submit` can target it going
> forward.
