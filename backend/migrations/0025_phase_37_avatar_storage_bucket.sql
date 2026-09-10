-- Phase 37: Supabase Storage bucket for user-uploaded avatars.
-- Run once in the Supabase SQL Editor. Written idempotently, but
-- **best-effort** — verify against the live project's Storage/RLS setup in
-- the dashboard before relying on it; this couldn't be tested against a
-- real Supabase instance from the repo.
--
-- Mobile uploads directly to this bucket using the signed-in user's own
-- JWT (via @supabase/supabase-js's built-in storage client — no backend
-- Storage API calls, no service role key needed). The backend only ever
-- writes the resulting public URL to profiles.avatar_url (see
-- app/auth/avatar_routes.py, PATCH /me/avatar).
--
-- Expected object path convention: "{auth.uid()}/avatar.<ext>" — the RLS
-- policies below check that the first path segment matches the requesting
-- user's own id, so a user can only write into their own folder.

INSERT INTO storage.buckets (id, name, public)
VALUES ('avatars', 'avatars', true)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Avatar images are publicly readable" ON storage.objects;
CREATE POLICY "Avatar images are publicly readable"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'avatars');

DROP POLICY IF EXISTS "Users can upload their own avatar" ON storage.objects;
CREATE POLICY "Users can upload their own avatar"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'avatars'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

DROP POLICY IF EXISTS "Users can replace their own avatar" ON storage.objects;
CREATE POLICY "Users can replace their own avatar"
    ON storage.objects FOR UPDATE
    USING (
        bucket_id = 'avatars'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );
