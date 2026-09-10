-- Phase 34: Per-device scheduled push delivery.
-- Run once in the Supabase SQL Editor. Safe to re-run (idempotent).
--
-- Lets a device register a preferred local delivery time for the daily
-- briefing push, instead of always getting it the instant the server-side
-- pipeline finishes. Kept on user_devices (not user_preferences) because
-- device registration requires no auth today (local-first) and this must
-- not change that.
--
-- notification_time: "HH:MM" 24h local time, or NULL = no preference
--   (device stays in the immediate-blast group, unchanged behavior).
-- timezone: IANA name (e.g. "America/Los_Angeles"), or NULL = falls back
--   to the server's SCHEDULER_TIMEZONE.
-- last_push_sent_date: prevents double-sending within the same local day.

ALTER TABLE user_devices ADD COLUMN IF NOT EXISTS notification_time TEXT;
ALTER TABLE user_devices ADD COLUMN IF NOT EXISTS timezone TEXT;
ALTER TABLE user_devices ADD COLUMN IF NOT EXISTS last_push_sent_date DATE;
