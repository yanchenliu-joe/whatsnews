-- Security hardening (2026-07-17) — response to Supabase Advisor findings.
--
-- Root cause: every table in `public` was created with Supabase's default
-- `GRANT ALL ON ALL TABLES` to the `anon` and `authenticated` roles, and
-- most had Row Level Security never enabled at all. Since this app's
-- Supabase anon key necessarily ships inside the mobile bundle (required
-- for Supabase Auth to work), this meant anyone extracting that key could
-- read/write/delete every row in these tables directly via Supabase's
-- PostgREST API, completely bypassing this backend, its business logic,
-- and its x-admin-key gating.
--
-- Confirmed via direct DB introspection + a code-wide grep before writing
-- this: none of the tables below are ever accessed by the mobile client
-- directly through supabase-js — every one of them is only ever touched by
-- this backend's own DATABASE_URL connection, which authenticates as the
-- `postgres` role. That role has `rolbypassrls = true` (confirmed live),
-- so enabling RLS here has zero effect on the backend itself — only on
-- the anon/authenticated roles Supabase's REST API uses.
--
-- Written idempotently (safe to re-run), but this is a live security
-- change against production data — it was run directly against the
-- Supabase SQL Editor / DATABASE_URL after the tables' access patterns
-- were verified, not blindly applied.

-- ── Part 1: enable RLS + revoke anon/authenticated grants on tables the
--    mobile client never touches directly (backend-only, via its own
--    postgres-role connection) ─────────────────────────────────────────
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'articles', 'daily_reports', 'editorial_perspectives',
    'editorial_watch_next', 'generation_runs', 'narrative_audio_variants',
    'product_events', 'saved_articles', 'topics', 'user_devices',
    'user_preferences', 'user_topics', 'users'
  ]
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon, authenticated;', t);
  END LOOP;
END $$;

-- ── Part 2: tables that already had RLS enabled with no policy (correctly
--    locked out already — Advisor flags this as "confirm intentional,"
--    which it is) — just tidy the same redundant broad grants for
--    consistency ───────────────────────────────────────────────────────
REVOKE ALL ON public.briefing_narratives FROM anon, authenticated;
REVOKE ALL ON public.entitlements FROM anon, authenticated;
REVOKE ALL ON public.news_sources FROM anon, authenticated;

-- ── Part 3: profiles — the one table with real user-scoped policies
--    already in place (view own / update own). Two fixes:
--    (a) Auth RLS Initialization Plan perf warning: bare auth.uid() is
--        re-evaluated per row; wrapping it in a scalar subquery lets
--        Postgres evaluate it once per query instead.
--    (b) Grants were still the default GRANT ALL — narrow to just
--        SELECT/UPDATE, matching what the two policies actually permit
--        (RLS already silently denies INSERT/DELETE with no matching
--        policy regardless, so this is cleanup, not a behavior change).
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile" ON public.profiles
  FOR SELECT USING ((select auth.uid()) = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile" ON public.profiles
  FOR UPDATE USING ((select auth.uid()) = id);

REVOKE ALL ON public.profiles FROM anon, authenticated;
GRANT SELECT, UPDATE ON public.profiles TO authenticated;
GRANT SELECT ON public.profiles TO anon;

-- ── Part 4: handle_new_user() trigger function — SECURITY DEFINER, was
--    directly callable by PUBLIC/anon/authenticated. Trigger firing (on
--    auth.users INSERT) does not require the inserting role to hold
--    EXECUTE on the trigger function, so this only closes an unnecessary
--    direct-invocation surface — the signup flow itself is unaffected.
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;

-- ── Part 5: missing indexes on foreign key columns (Advisor performance
--    finding) — speeds up joins/cascade-deletes on these columns. Safe,
--    purely additive.
CREATE INDEX IF NOT EXISTS idx_articles_report_id ON public.articles (report_id);
CREATE INDEX IF NOT EXISTS idx_articles_topic_id ON public.articles (topic_id);
CREATE INDEX IF NOT EXISTS idx_briefing_narratives_topic_id ON public.briefing_narratives (topic_id);
CREATE INDEX IF NOT EXISTS idx_news_sources_topic_id ON public.news_sources (topic_id);
CREATE INDEX IF NOT EXISTS idx_saved_articles_article_id ON public.saved_articles (article_id);
CREATE INDEX IF NOT EXISTS idx_user_topics_topic_id ON public.user_topics (topic_id);

-- ── Explicitly NOT done here (see docs/ENGINEERING.md for the reasoning) ──
-- - Storage "Public Bucket Allows Listing" (avatars/narrative-audio) — low
--   severity, and a real fix means moving off public buckets + plain
--   <img>/audio src URLs to signed URLs, a bigger behavior change than
--   this pass's scope.
-- - Auth "Leaked Password Protection Disabled" — an Auth-service setting,
--   not a SQL/table change; needs a manual toggle in the Supabase
--   dashboard (Authentication → Policies / Providers).
-- - "Unused Index" findings — left alone; Advisor's usage stats are a
--   point-in-time signal, not proof an index is safe to drop.
