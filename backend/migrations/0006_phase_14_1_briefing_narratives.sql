-- Phase 14.1: Morning Intelligence Briefing narrative scripts
-- Run once in Supabase SQL Editor. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS briefing_narratives (
    id                          SERIAL PRIMARY KEY,
    report_date                 DATE NOT NULL,
    scope                       TEXT NOT NULL DEFAULT 'daily',
    topic_id                    INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    version                     INTEGER NOT NULL DEFAULT 1,
    status                      TEXT NOT NULL DEFAULT 'pending',
    script_json                 JSONB NOT NULL DEFAULT '{}',
    script_text                 TEXT NOT NULL DEFAULT '',
    word_count                  INTEGER,
    estimated_duration_seconds  INTEGER,
    article_refs                JSONB NOT NULL DEFAULT '[]',
    generation_method           TEXT NOT NULL DEFAULT 'rule_v1',
    model                       TEXT,
    error_message               TEXT,
    generated_at                TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (scope, report_date, topic_id, version)
);

CREATE INDEX IF NOT EXISTS idx_briefing_narratives_date_scope_status
    ON briefing_narratives (report_date DESC, scope, status);
