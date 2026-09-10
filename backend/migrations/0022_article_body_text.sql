-- Migration 0022: Add body_text column to articles
-- Stores full article text extracted from RSS entry.content (when provided by feed).
-- Falls back gracefully — existing rows keep body_text = NULL.

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS body_text TEXT;
