-- Phase 19: Article image URL
-- Stores the best available image extracted from the RSS feed entry at ingestion time.
-- NULL for articles ingested before this migration or feeds that carry no image.

ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;
