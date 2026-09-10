-- Phase 9.1E: Geopolitics source tuning
-- Run once in the Supabase SQL Editor. Safe to re-run (idempotent).
--
-- Changes:
--   1. Disable Guardian World for Geopolitics (0% quality-pass due to paywall teasers).
--   2. Al Jazeera World: NO CHANGE — investigation found no stable narrower RSS feed
--      (see notes below).
--
-- Al Jazeera investigation (2026-06-22):
--   - Current feed: https://www.aljazeera.com/xml/rss/all.xml (only official RSS)
--   - Tested section URLs (all 404): /news/rss, /xml/rss/news.xml,
--     /xml/rss/middle-east.xml, /xml/rss/world.xml, /middle-east/rss,
--     /topics/middle-east/rss, /tag/world/rss, feeds.aljazeera.com/*
--   - Middle-east and news pages link only to /xml/rss/all.xml
--   - Legacy feeds.aljazeera.com subdomain is unreachable
--   => Leave Al Jazeera unchanged until Al Jazeera publishes a section feed.

-- 1. Disable Guardian World (Geopolitics only) --------------------------------

UPDATE news_sources
SET is_active = FALSE
WHERE name = 'Guardian World'
  AND feed_url = 'https://www.theguardian.com/world/rss'
  AND topic_id = (SELECT id FROM topics WHERE name = 'Geopolitics');

-- 2. Verify -------------------------------------------------------------------

-- Expected: Guardian World is_active = FALSE; 4 active Geopolitics sources remain.
SELECT t.name AS topic,
       ns.name AS source_name,
       ns.is_active,
       ns.feed_url
FROM news_sources ns
JOIN topics t ON t.id = ns.topic_id
WHERE t.name = 'Geopolitics'
ORDER BY ns.is_active DESC, ns.name;

-- Expected counts: 4 active, 1 inactive (Guardian World).
SELECT is_active, COUNT(*) AS source_count
FROM news_sources ns
JOIN topics t ON t.id = ns.topic_id
WHERE t.name = 'Geopolitics'
GROUP BY is_active
ORDER BY is_active DESC;
