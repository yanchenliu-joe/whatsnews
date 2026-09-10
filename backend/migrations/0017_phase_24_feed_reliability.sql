-- Phase 24.1: Feed reliability tracking columns on news_sources
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- Extends news_sources with per-feed health metrics tracked by the ingestion engine.
-- Auto-disable rule: consecutive_failures >= 5 → is_active set to FALSE by application.
-- Auto-recovery: application re-enables when a previously failing feed succeeds 3× consecutively.

ALTER TABLE news_sources
    ADD COLUMN IF NOT EXISTS failure_count         INT            DEFAULT 0,
    ADD COLUMN IF NOT EXISTS success_count         INT            DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consecutive_failures  INT            DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consecutive_successes INT            DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_success_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_failure_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS auto_disabled_at      TIMESTAMPTZ;

-- Index to quickly find feeds that may need re-enabling or are degraded.
CREATE INDEX IF NOT EXISTS idx_news_sources_consecutive_failures
    ON news_sources (consecutive_failures)
    WHERE is_active = TRUE;

-- Verify
-- SELECT COUNT(*) AS total_sources,
--        COUNT(*) FILTER (WHERE failure_count > 0) AS ever_failed,
--        COUNT(*) FILTER (WHERE consecutive_failures >= 5) AS auto_disabled
-- FROM news_sources;
