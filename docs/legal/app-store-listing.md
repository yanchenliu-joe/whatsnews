# App Store Connect listing draft

Draft copy for the App Store Connect listing. Edit freely — this is a
starting point grounded in what the app actually does today (free, no
subscriptions, 20 topics, on-device voice, 12-language UI).

## App name (30 char max)
WhatsNews: Daily Briefing

## Subtitle (30 char max)
News, briefed. Read or listen.

## Promotional text (170 char max, editable without re-review)
One daily briefing across 20 topics — curated, concise, and read aloud
on your device. No subscription, no clutter, no infinite scroll.

## Description

WhatsNews delivers one focused news briefing a day — not an endless
feed. Every morning, we scan hundreds of sources across 20 topics, pick
the stories that matter, and explain why each one matters to you.

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
Missed a day? Every past briefing is saved and searchable, going back as
far as you've had the app installed.

BUILD YOUR STREAK
Track your daily reading streak, unlock milestones, and see your
reading history on a calendar.

YOUR TOPICS, YOUR LANGUAGE
Choose which of 20 topics you follow. Read the app itself in any of 12
languages, with full right-to-left support for Arabic and Urdu.

FREE, NO CATCH
WhatsNews is completely free. No subscription, no ads, no paywalled
articles.

An account is optional — you can use WhatsNews fully without signing in.
Sign in only if you want your saved articles and preferences to follow
you across devices.

## Keywords (100 char max, comma-separated, no spaces after commas)
news,briefing,daily news,news summary,news digest,current events,news app,voice news,text to speech

## Support URL
mailto:contact@whatsnewsbrief.com
<!-- no dedicated support page exists; a contact-form-style mailto is enough for App Store Connect -->

## Marketing URL (optional)
https://whatsnewsbrief.com

## Privacy Policy URL (required)
https://whatsnewsbrief.com/privacy

## Category
Primary: News
Secondary: (optional) Productivity

## Age Rating questionnaire
The app has no user-generated content visible to other users, no
gambling, no mature/violent content of its own — content is curated news
summaries from mainstream RSS sources. Answer "None" / "No" to most
Apple age-rating questions; likely lands at 12+ or 17+ solely due to
"Unrestricted Web Access" if the in-app WebView (Article Detail's "Web
mode" toggle) counts as such — double check this specific question when
filling out the questionnaire, since it loads arbitrary third-party
article URLs.

## App Privacy (Data collection) questionnaire

Based on `docs/legal/privacy-policy.md`, expect to declare:

| Data type | Collected? | Linked to user? | Used for |
|---|---|---|---|
| Email Address | Yes (optional account) | Yes | App Functionality |
| Name | Yes (optional display name) | Yes | App Functionality |
| Photos (profile picture) | Yes (optional) | Yes | App Functionality |
| User ID | Yes | Yes | App Functionality |
| Push Token / Device ID | Yes | No (anonymous) | App Functionality |
| Crash Data | Yes (Sentry) | No | App Functionality, Analytics |
| Product Interaction (analytics events) | Yes | No | Analytics |

Declare **no** tracking for advertising purposes, **no** third-party ad
SDKs, **no** location, **no** contacts, **no** financial/payment info
(no in-app purchases exist).

## Export Compliance
`app.json` already sets `ios.infoPlist.ITSAppUsesNonExemptEncryption:
false` (standard HTTPS/TLS only, no custom encryption) — App Store
Connect should not prompt for this separately during submission.

## Screenshots needed
6.7" (iPhone 15 Pro Max class) and 6.5" (iPhone 11 Pro Max class) are the
two mandatory sizes; iPad not needed since `supportsTablet: false`.
Suggested shots: Briefing tab (main feed), an open article with "Why It
Matters", the voice playback card, the Archive/history calendar or date
list, the Streak tab, and the Account/language screen.
