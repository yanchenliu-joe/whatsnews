-- Phase 11.2: Topic expansion — Business, Defense
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- Adds 2 topics (sort_order 8–9) and 5 validated RSS sources per topic (10 total).
-- Uses news_sources.feed_url (not url). No Reuters or known-unstable feeds.
--
-- Feed validation notes (2026-06-23):
--   Business: Crunchbase News skews macro; FT Companies overlaps Markets paywall risk.
--             Selected Fortune, Inc.com, and Industry Dive verticals (corporate focus).
--   Defense: Military.com RSS parse error; National Defense Magazine mismatched tag.
--            Defense One skews diplomacy; replaced with USNI News (naval/procurement).

-- 1. Topics -------------------------------------------------------------------

INSERT INTO topics (name, is_active, sort_order)
SELECT v.name, TRUE, v.sort_order
FROM (
    VALUES
        ('Business',  8),
        ('Defense',   9)
) AS v(name, sort_order)
WHERE NOT EXISTS (
    SELECT 1 FROM topics t WHERE t.name = v.name
);

-- 2. RSS sources --------------------------------------------------------------
-- Guarded by NOT EXISTS on (topic_id, feed_url) so re-running never duplicates.

INSERT INTO news_sources (topic_id, name, feed_url, source_type, is_active)
SELECT t.id, v.name, v.feed_url, 'rss', TRUE
FROM topics t
JOIN (
    VALUES
        -- Business (5 feeds) — companies, M&A, leadership, enterprise (not macro)
        ('Business', 'Fortune',           'https://fortune.com/feed/'),
        ('Business', 'Inc.com',           'https://www.inc.com/rss/'),
        ('Business', 'Retail Dive',       'https://www.retaildive.com/feeds/news/'),
        ('Business', 'CFO Dive',          'https://www.cfodive.com/feeds/news/'),
        ('Business', 'Supply Chain Dive', 'https://www.supplychaindive.com/feeds/news/'),

        -- Defense (5 feeds) — industry, procurement, mil-tech (not diplomacy)
        ('Defense', 'Defense News',     'https://www.defensenews.com/arc/outboundfeeds/rss/'),
        ('Defense', 'Breaking Defense', 'https://breakingdefense.com/feed/'),
        ('Defense', 'The War Zone',     'https://www.twz.com/feed'),
        ('Defense', 'C4ISRNET',         'https://www.c4isrnet.com/arc/outboundfeeds/rss/'),
        ('Defense', 'USNI News',        'https://news.usni.org/feed')
) AS v(topic_name, name, feed_url) ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);

-- Disable unreliable feeds if a prior run inserted them.
UPDATE news_sources
SET is_active = FALSE
WHERE feed_url IN (
    'https://www.military.com/rss/news',
    'https://www.nationaldefensemagazine.org/rss/articles',
    'https://www.defenseone.com/rss/all/'
);

-- 3. Verify -------------------------------------------------------------------
-- Expected: 10 topics total; 10 new sources (5 per new topic).
-- SELECT t.name, t.sort_order, t.is_active, COUNT(ns.id) AS source_count
-- FROM topics t
-- LEFT JOIN news_sources ns ON ns.topic_id = t.id AND ns.is_active = TRUE
-- GROUP BY t.id, t.name, t.sort_order, t.is_active
-- ORDER BY t.sort_order;
