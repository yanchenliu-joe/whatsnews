-- Phase 24.2: Feed lifecycle state management
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- feed_state lifecycle:
--   active    → healthy feed, fetched every run
--   degraded  → quality declining (3+ consecutive failures), fetched every other run
--   paused    → admin-suppressed or auto-throttled, never auto-fetched
--   disabled  → is_active = FALSE (already handled by existing logic)
--
-- skip_next_run: throttle flag for degraded feeds (alternates TRUE/FALSE each run)
-- replace_flag:  admin-marked this feed for replacement
-- replace_reason: free-text reason for replacement intent

ALTER TABLE news_sources
    ADD COLUMN IF NOT EXISTS feed_state    VARCHAR(20) DEFAULT 'active'
        CHECK (feed_state IN ('active', 'degraded', 'paused', 'disabled')),
    ADD COLUMN IF NOT EXISTS skip_next_run BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS replace_flag  BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS replace_reason TEXT;

-- Backfill state for feeds that already have reliability history.
-- Feeds with 3+ consecutive failures → degraded.
-- Feeds with is_active = FALSE → disabled.
UPDATE news_sources
SET feed_state = 'disabled'
WHERE is_active = FALSE
  AND feed_state = 'active';

UPDATE news_sources
SET feed_state = 'degraded'
WHERE consecutive_failures >= 3
  AND is_active = TRUE
  AND feed_state = 'active';

CREATE INDEX IF NOT EXISTS idx_news_sources_feed_state
    ON news_sources (feed_state)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_news_sources_replace_flag
    ON news_sources (replace_flag)
    WHERE replace_flag = TRUE;

-- Verify:
-- SELECT feed_state, COUNT(*) AS cnt FROM news_sources GROUP BY feed_state ORDER BY cnt DESC;
