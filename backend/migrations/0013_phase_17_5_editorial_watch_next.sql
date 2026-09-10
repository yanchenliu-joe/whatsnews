-- Phase 17.5: Daily Watch Next aggregation.
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS editorial_watch_next (
    id                  SERIAL PRIMARY KEY,
    report_date         DATE NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    watch_json          JSONB NOT NULL DEFAULT '{}',
    item_count          INTEGER NOT NULL DEFAULT 0,
    generation_method   TEXT NOT NULL DEFAULT 'rule_v1',
    error_message       TEXT,
    version             INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_date, version)
);

CREATE INDEX IF NOT EXISTS idx_editorial_watch_next_date_status
    ON editorial_watch_next (report_date DESC, status);
