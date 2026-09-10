-- Phase 17.1: Editorial metadata on selected articles.
-- Stores rule-based editorial profile from the Editorial Engine.

ALTER TABLE articles ADD COLUMN IF NOT EXISTS editorial_metadata JSONB;

CREATE INDEX IF NOT EXISTS idx_articles_editorial_metadata
    ON articles USING gin (editorial_metadata)
    WHERE editorial_metadata IS NOT NULL;
