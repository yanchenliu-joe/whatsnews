-- Phase 7.2A: Real News Ingestion schema preparation
-- Run this once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- NOTE: This project's news_sources table uses `feed_url` (not `url`) to stay
-- compatible with the existing ingestion code (app/ingestion.py, seed.py).
-- All statements use IF NOT EXISTS / guarded inserts so running on the current
-- database is a no-op for anything that already exists.

-- 1. news_sources -------------------------------------------------------------
-- Registered RSS sources per topic. topic_id references the integer topics.id.
CREATE TABLE IF NOT EXISTS news_sources (
    id          SERIAL PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    feed_url    TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'rss',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Backward-compatible article columns for ingestion ------------------------
-- published_at and content_hash already exist from earlier phases; these two
-- are the genuinely new columns this phase adds.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS raw_url     TEXT;

-- 3. Unique dedup index on content_hash (non-null only) -----------------------
-- Already present on the current DB; included so a fresh setup also gets it.
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_content_hash
    ON articles (content_hash)
    WHERE content_hash IS NOT NULL;

-- 4. Seed RSS sources for existing topics -------------------------------------
-- Joins by topic name so it works with whatever integer ids the topics have.
-- Guarded by NOT EXISTS so re-running never creates duplicates.
INSERT INTO news_sources (topic_id, name, feed_url, source_type, is_active)
SELECT t.id, v.name, v.feed_url, 'rss', TRUE
FROM topics t
JOIN (
    VALUES
        ('Artificial Intelligence', 'TechCrunch AI',            'https://techcrunch.com/category/artificial-intelligence/feed/'),
        ('Artificial Intelligence', 'The Verge AI',             'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'),
        ('Artificial Intelligence', 'MIT Technology Review AI', 'https://www.technologyreview.com/topic/artificial-intelligence/feed'),
        ('Climate Change',          'Carbon Brief',             'https://www.carbonbrief.org/feed/'),
        ('Climate Change',          'The Guardian Climate',     'https://www.theguardian.com/environment/climate-crisis/rss'),
        ('Climate Change',          'Reuters Climate',          'https://www.reuters.com/business/environment/rss')
) AS v(topic_name, name, feed_url) ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);
