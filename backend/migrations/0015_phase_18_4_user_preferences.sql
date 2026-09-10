-- Phase 18.4: Per-user preferences (JSONB).
-- Run once in Supabase SQL editor or via psql. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id         UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    preferences     JSONB NOT NULL DEFAULT '{}',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_updated_at
    ON user_preferences (updated_at DESC);
