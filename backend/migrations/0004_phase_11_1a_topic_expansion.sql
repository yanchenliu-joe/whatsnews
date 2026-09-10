-- Phase 11.1A: Topic expansion — Healthcare, Energy, Cybersecurity
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- Adds 3 topics (sort_order 5–7) and 5 validated RSS sources per topic (15 total).
-- Uses news_sources.feed_url (not url). No Reuters or known-unstable feeds.
--
-- Feed validation notes (2026-06-23):
--   Healthcare: NIH RSS returns 403; replaced with FDA Press Releases.
--   Energy: E&E News and World Oil return 404; replaced with EIA + Power Engineering.
--   Cybersecurity: CISA all.xml fails feedparser (mismatched tag); use SecurityWeek.

-- 1. Topics -------------------------------------------------------------------

INSERT INTO topics (name, is_active, sort_order)
SELECT v.name, TRUE, v.sort_order
FROM (
    VALUES
        ('Healthcare',      5),
        ('Energy',          6),
        ('Cybersecurity',   7)
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
        -- Healthcare (5 feeds)
        ('Healthcare', 'STAT News',           'https://www.statnews.com/feed/'),
        ('Healthcare', 'Fierce Healthcare',   'https://www.fiercehealthcare.com/rss/xml'),
        ('Healthcare', 'MedPage Today',       'https://www.medpagetoday.com/rss/headlines.xml'),
        ('Healthcare', 'BBC Health',          'https://feeds.bbci.co.uk/news/health/rss.xml'),
        ('Healthcare', 'FDA Press Releases',  'https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml'),

        -- Energy (5 feeds)
        ('Energy', 'Oilprice.com',            'https://oilprice.com/rss/main'),
        ('Energy', 'Utility Dive',            'https://www.utilitydive.com/feeds/news/'),
        ('Energy', 'FT Energy',               'https://www.ft.com/energy?format=rss'),
        ('Energy', 'EIA Today in Energy',     'https://www.eia.gov/rss/todayinenergy.xml'),
        ('Energy', 'Power Engineering',       'https://www.power-eng.com/feed/'),

        -- Cybersecurity (5 feeds)
        ('Cybersecurity', 'Krebs on Security',    'https://krebsonsecurity.com/feed/'),
        ('Cybersecurity', 'BleepingComputer',     'https://www.bleepingcomputer.com/feed/'),
        ('Cybersecurity', 'Dark Reading',         'https://www.darkreading.com/rss.xml'),
        ('Cybersecurity', 'The Hacker News',      'https://feeds.feedburner.com/TheHackersNews'),
        ('Cybersecurity', 'SecurityWeek',         'https://www.securityweek.com/feed/')
) AS v(topic_name, name, feed_url) ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);

-- Disable CISA feed if a prior run inserted it (feedparser parse error).
UPDATE news_sources
SET is_active = FALSE
WHERE feed_url = 'https://www.cisa.gov/cybersecurity-advisories/all.xml';

-- 3. Verify -------------------------------------------------------------------
-- Expected: 8 topics total; 15 new sources (5 per new topic).
-- SELECT t.name, t.sort_order, t.is_active, COUNT(ns.id) AS source_count
-- FROM topics t
-- LEFT JOIN news_sources ns ON ns.topic_id = t.id AND ns.is_active = TRUE
-- GROUP BY t.id, t.name, t.sort_order, t.is_active
-- ORDER BY t.sort_order;
