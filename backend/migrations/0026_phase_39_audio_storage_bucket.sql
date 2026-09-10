-- Phase 39: Supabase Storage bucket for narrative TTS audio (2026-07-07).
-- Run once in the Supabase SQL Editor. Written idempotently, but
-- **best-effort** — verify against the live project's Storage/RLS setup in
-- the dashboard before relying on it; this couldn't be tested against a
-- real Supabase instance from the repo.
--
-- Unlike the "avatars" bucket (migration 0025), which mobile writes to
-- directly using the signed-in user's own JWT, this bucket is written to
-- ONLY by the backend using the Supabase service-role key (SUPABASE_SERVICE_
-- ROLE_KEY, which bypasses RLS entirely) — narrative audio is server-
-- generated content, not user-uploaded. So only a public-read policy is
-- needed here; no INSERT/UPDATE policy for anon/authenticated roles.
--
-- Driven by moving off Render's ephemeral filesystem (audio files under
-- media/audio/ would be wiped on every redeploy, permanently breaking
-- Archive/History voice playback for every past date with no auto-
-- recovery) to Supabase Storage, which persists independent of the
-- backend's own hosting/deploys.

INSERT INTO storage.buckets (id, name, public)
VALUES ('narrative-audio', 'narrative-audio', true)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Narrative audio is publicly readable" ON storage.objects;
CREATE POLICY "Narrative audio is publicly readable"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'narrative-audio');
