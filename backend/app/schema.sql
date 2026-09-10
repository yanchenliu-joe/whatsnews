-- WhatsNews database schema
-- Run this once in your Supabase SQL editor (or via psql) to create all tables.

-- Users (created now, used from Phase 4 onward for auth)
CREATE TABLE IF NOT EXISTS users (
    id      SERIAL PRIMARY KEY,
    email   TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Topics that the app tracks (e.g. "Artificial Intelligence", "Climate")
CREATE TABLE IF NOT EXISTS topics (
    id      SERIAL PRIMARY KEY,
    name    TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Which topics a user has subscribed to
CREATE TABLE IF NOT EXISTS user_topics (
    user_id  INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, topic_id)
);

-- A single daily report for one topic on one date
CREATE TABLE IF NOT EXISTS daily_reports (
    id          SERIAL PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    report_date DATE    NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (topic_id, report_date)
);

-- Records each report generation run for observability and debugging
CREATE TABLE IF NOT EXISTS generation_runs (
    id                       SERIAL PRIMARY KEY,
    topic                    TEXT NOT NULL,
    trigger_type             TEXT NOT NULL,        -- 'scheduler' | 'admin'
    status                   TEXT NOT NULL,        -- 'running' | 'success' | 'failed'
    report_date              DATE,
    started_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at              TIMESTAMPTZ,
    duration_ms              INTEGER,
    articles_count           INTEGER DEFAULT 0,
    ai_refine_attempted      INTEGER DEFAULT 0,
    ai_refine_success_count  INTEGER DEFAULT 0,
    ai_refine_fallback_count INTEGER DEFAULT 0,
    error_message            TEXT,
    meta_json                JSONB
);

-- Individual news articles that belong to a daily report
CREATE TABLE IF NOT EXISTS articles (
    id              SERIAL PRIMARY KEY,
    report_id       INTEGER NOT NULL REFERENCES daily_reports(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    summary         TEXT,
    source          TEXT,
    url             TEXT,
    why_it_matters  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- If the table already exists, add the column without dropping anything.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS why_it_matters TEXT;

-- Phase 7.0A: make topics the single source of truth.
-- Safe to run on an existing database — existing topics remain active with sort_order=0.
ALTER TABLE topics ADD COLUMN IF NOT EXISTS is_active  BOOLEAN  NOT NULL DEFAULT TRUE;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS sort_order INTEGER  NOT NULL DEFAULT 0;

-- Phase 7.2A: Real news ingestion schema foundation.

-- Registered news sources (RSS feeds, API endpoints, etc.) per topic.
CREATE TABLE IF NOT EXISTS news_sources (
    id          SERIAL PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'rss',
    feed_url    TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Articles: add columns for real ingestion support.
-- content_hash: SHA-256 of title+url for deduplication.
-- raw_summary:  original summary from the feed before any processing.
-- fetched_at:   when the article was fetched from the source.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS raw_summary  TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS fetched_at   TIMESTAMPTZ;

-- Phase 7.2B.1: Decouple ingestion from report creation.
-- Ingested articles belong to a topic but are not yet assigned to a report.
-- report_id becomes nullable so articles can exist before report assembly.
-- topic_id gives ingested articles a direct link to their topic.
ALTER TABLE articles ALTER COLUMN report_id DROP NOT NULL;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE;

-- Phase 7.3D: Article publish date for recency-based selection.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

-- Phase 17.1: Editorial Intelligence metadata (see migrations/0009).
ALTER TABLE articles ADD COLUMN IF NOT EXISTS editorial_metadata JSONB;

-- Phase 7.2A: Ingestion provenance columns (see migrations/0001_phase_7_2a_news_ingestion.sql).
ALTER TABLE articles ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS raw_url     TEXT;

-- Phase 7.2A.1: Replace per-report dedup with global dedup.
-- A given content_hash can only exist once across all reports, so the
-- ingestion pipeline can deduplicate without knowing the report_id first,
-- and stale articles from previous days' feeds are silently skipped.
-- Partial: existing seed rows (NULL content_hash) are unaffected.
DROP INDEX IF EXISTS idx_articles_report_content_hash;
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_content_hash
    ON articles (content_hash)
    WHERE content_hash IS NOT NULL;

-- Phase 8.2: Push notification device registration.
-- Phase 34: notification_time/timezone/last_push_sent_date for per-device
-- scheduled push delivery (see migration 0024).
CREATE TABLE IF NOT EXISTS user_devices (
    id                    SERIAL PRIMARY KEY,
    push_token            TEXT UNIQUE NOT NULL,
    platform              TEXT,
    notification_time     TEXT,
    timezone              TEXT,
    last_push_sent_date   DATE,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Phase 8.6: Lightweight product event tracking.
CREATE TABLE IF NOT EXISTS product_events (
    id            SERIAL PRIMARY KEY,
    event_name    TEXT NOT NULL,
    article_id    INTEGER,
    topic_name    TEXT,
    metadata_text TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_events_name_created
    ON product_events (event_name, created_at DESC);

-- Phase 14.1: Morning Intelligence Briefing narrative scripts (see migrations/0006).
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

ALTER TABLE briefing_narratives
    ADD COLUMN IF NOT EXISTS audio_status TEXT NOT NULL DEFAULT 'not_generated',
    ADD COLUMN IF NOT EXISTS audio_url TEXT,
    ADD COLUMN IF NOT EXISTS audio_storage_path TEXT,
    ADD COLUMN IF NOT EXISTS audio_duration_seconds INTEGER,
    ADD COLUMN IF NOT EXISTS audio_voice TEXT,
    ADD COLUMN IF NOT EXISTS audio_model TEXT,
    ADD COLUMN IF NOT EXISTS audio_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS audio_error_message TEXT;

CREATE INDEX IF NOT EXISTS idx_briefing_narratives_audio_status
    ON briefing_narratives (report_date DESC, audio_status);

CREATE TABLE IF NOT EXISTS narrative_audio_variants (
    id                      BIGSERIAL PRIMARY KEY,
    narrative_id            BIGINT NOT NULL REFERENCES briefing_narratives(id) ON DELETE CASCADE,
    voice_profile           TEXT NOT NULL CHECK (voice_profile IN ('female', 'male')),
    audio_status            TEXT NOT NULL DEFAULT 'not_generated',
    audio_url               TEXT,
    audio_storage_path      TEXT,
    audio_duration_seconds  INTEGER,
    audio_provider_voice    TEXT,
    audio_model             TEXT,
    audio_generated_at      TIMESTAMPTZ,
    audio_error_message     TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (narrative_id, voice_profile)
);

CREATE INDEX IF NOT EXISTS idx_narrative_audio_variants_narrative
    ON narrative_audio_variants (narrative_id);

-- Phase 17.3: Daily editorial perspective (see migrations/0010).
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

-- Phase 17.5: Daily Watch Next aggregation (see migrations/0013).
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
