-- Phase 18.3: User saved articles (bookmark sync).
-- Run once in Supabase SQL editor or via psql. Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS saved_articles (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    article_id      INTEGER REFERENCES articles(id) ON DELETE SET NULL,
    article_url     TEXT NOT NULL,
    article_title   TEXT,
    topic           TEXT,
    source          TEXT,
    summary         TEXT,
    why_it_matters  TEXT,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_articles_user_saved_at
    ON saved_articles (user_id, saved_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_articles_user_url
    ON saved_articles (user_id, article_url);

CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_articles_user_article_id
    ON saved_articles (user_id, article_id)
    WHERE article_id IS NOT NULL;
