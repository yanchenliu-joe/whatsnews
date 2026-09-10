-- Phase 25: Add image_url to saved_articles table.
-- Safe to re-run (IF NOT EXISTS guard).

ALTER TABLE saved_articles ADD COLUMN IF NOT EXISTS image_url TEXT;
