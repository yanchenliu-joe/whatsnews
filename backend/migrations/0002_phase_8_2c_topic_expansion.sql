-- Phase 8.2C: Topic expansion — Technology, Markets, Geopolitics
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- Adds 3 topics (sort_order 2–4, after existing AI=0 and Climate=1)
-- and 5 RSS sources per topic (15 total).
-- Uses news_sources.feed_url (not url). No Reuters or known-unstable feeds.

-- 1. Topics -------------------------------------------------------------------

INSERT INTO topics (name, is_active, sort_order)
SELECT v.name, TRUE, v.sort_order
FROM (
    VALUES
        ('Technology',  2),
        ('Markets',     3),
        ('Geopolitics', 4)
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
        -- Technology (5 feeds)
        ('Technology', 'The Register',         'https://www.theregister.com/headlines.atom'),
        ('Technology', 'Ars Technica',         'https://feeds.arstechnica.com/arstechnica/index'),
        ('Technology', 'Wired Business',       'https://www.wired.com/feed/category/business/latest/rss'),
        ('Technology', 'Hacker News Front Page', 'https://hnrss.org/frontpage'),
        ('Technology', 'Techmeme',             'https://www.techmeme.com/feed.xml'),

        -- Markets (5 feeds)
        ('Markets', 'CNBC Markets',            'https://www.cnbc.com/id/100003114/device/rss/rss.html'),
        ('Markets', 'MarketWatch Top Stories', 'https://feeds.content.dowjones.io/public/rss/mw_topstories'),
        ('Markets', 'Yahoo Finance',           'https://finance.yahoo.com/news/rssindex'),
        ('Markets', 'BBC Business',            'https://feeds.bbci.co.uk/news/business/rss.xml'),
        ('Markets', 'FT Markets',              'https://www.ft.com/markets?format=rss'),

        -- Geopolitics (5 feeds)
        ('Geopolitics', 'BBC World',           'https://feeds.bbci.co.uk/news/world/rss.xml'),
        ('Geopolitics', 'NYT World',           'https://rss.nytimes.com/services/xml/rss/nyt/World.xml'),
        ('Geopolitics', 'Guardian World',      'https://www.theguardian.com/world/rss'),
        ('Geopolitics', 'Al Jazeera World',    'https://www.aljazeera.com/xml/rss/all.xml'),
        ('Geopolitics', 'The Diplomat',        'https://thediplomat.com/feed/')
) AS v(topic_name, name, feed_url) ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);

-- 3. Verify -------------------------------------------------------------------
-- Expected: 5 topics total; 15 new sources (5 per new topic).
-- SELECT t.name, t.sort_order, t.is_active, COUNT(ns.id) AS source_count
-- FROM topics t
-- LEFT JOIN news_sources ns ON ns.topic_id = t.id AND ns.is_active = TRUE
-- GROUP BY t.id, t.name, t.sort_order, t.is_active
-- ORDER BY t.sort_order;
