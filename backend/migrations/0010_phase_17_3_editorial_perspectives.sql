-- Phase 17.3: Daily editorial perspective (product editorial judgment).
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS editorial_perspectives (
    id                      SERIAL PRIMARY KEY,
    report_date             DATE NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'pending',
    perspective_json        JSONB NOT NULL DEFAULT '{}',
    headline                TEXT,
    perspective_text        TEXT,
    confidence              TEXT,
    themes                  JSONB NOT NULL DEFAULT '[]',
    supporting_article_ids  JSONB NOT NULL DEFAULT '[]',
    generation_method       TEXT NOT NULL DEFAULT 'rule_v1',
    error_message           TEXT,
    version                 INTEGER NOT NULL DEFAULT 1,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_date, version)
);

CREATE INDEX IF NOT EXISTS idx_editorial_perspectives_date_status
    ON editorial_perspectives (report_date DESC, status);
