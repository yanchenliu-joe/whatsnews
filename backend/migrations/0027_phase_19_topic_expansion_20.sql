-- Phase 19: Topic expansion — 10→20 topics
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- Adds 10 topics (sort_order 10–19) and 5 validated RSS sources per topic (50 total).
-- Uses news_sources.feed_url (not url). All feeds are publicly accessible RSS/Atom.
--
-- New topics:
--   10  Science         research breakthroughs, academic discoveries, biology/physics
--   11  Crypto          digital assets, blockchain, DeFi, regulation
--   12  Real Estate     housing market, commercial real estate, proptech
--   13  Politics        US domestic politics, legislation, elections
--   14  Space           exploration, satellites, astronomy, commercial space
--   15  Education       K-12, higher education, EdTech, workforce
--   16  Labor           employment, wages, unions, workforce trends
--   17  Sports          major sports results and business
--   18  Entertainment   film, TV, music, streaming
--   19  Transportation  EVs, aviation, infrastructure, logistics

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Topics
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO topics (name, is_active, sort_order)
SELECT v.name, TRUE, v.sort_order
FROM (
    VALUES
        ('Science',         10),
        ('Crypto',          11),
        ('Real Estate',     12),
        ('Politics',        13),
        ('Space',           14),
        ('Education',       15),
        ('Labor',           16),
        ('Sports',          17),
        ('Entertainment',   18),
        ('Transportation',  19)
) AS v(name, sort_order)
WHERE NOT EXISTS (
    SELECT 1 FROM topics t WHERE t.name = v.name
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. RSS sources  (5 per topic, 50 total)
-- Guarded by NOT EXISTS on (topic_id, feed_url) so re-running never duplicates.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO news_sources (topic_id, name, feed_url, source_type, is_active)
SELECT t.id, v.name, v.feed_url, 'rss', TRUE
FROM topics t
JOIN (
    VALUES

        -- ── Science (5 feeds) ─────────────────────────────────────────────
        -- Quanta, ScienceDaily, New Scientist, Live Science, EurekAlert
        ('Science', 'Quanta Magazine',    'https://www.quantamagazine.org/feed/'),
        ('Science', 'ScienceDaily',       'https://www.sciencedaily.com/rss/all.xml'),
        ('Science', 'New Scientist',      'https://www.newscientist.com/feed/home/'),
        ('Science', 'Live Science',       'https://www.livescience.com/feeds/all'),
        ('Science', 'EurekAlert',         'https://www.eurekalert.org/rss.xml'),

        -- ── Crypto & Web3 (5 feeds) ───────────────────────────────────────
        -- CoinDesk, Cointelegraph, Decrypt, The Block, Bitcoin Magazine
        ('Crypto', 'CoinDesk',           'https://www.coindesk.com/arc/outboundfeeds/rss/'),
        ('Crypto', 'Cointelegraph',      'https://cointelegraph.com/rss'),
        ('Crypto', 'Decrypt',            'https://decrypt.co/feed'),
        ('Crypto', 'The Block',          'https://www.theblock.co/rss.xml'),
        ('Crypto', 'Bitcoin Magazine',   'https://bitcoinmagazine.com/.rss/full/'),

        -- ── Real Estate (5 feeds) ─────────────────────────────────────────
        -- HousingWire, The Real Deal, Inman, Bisnow, Commercial Observer
        ('Real Estate', 'HousingWire',          'https://www.housingwire.com/feed/'),
        ('Real Estate', 'The Real Deal',        'https://therealdeal.com/feed/'),
        ('Real Estate', 'Inman',                'https://www.inman.com/feed/'),
        ('Real Estate', 'Bisnow',               'https://www.bisnow.com/rss'),
        ('Real Estate', 'Commercial Observer',  'https://commercialobserver.com/feed/'),

        -- ── Politics (5 feeds) ────────────────────────────────────────────
        -- US domestic: Politico, The Hill, NPR Politics, Roll Call, Axios
        ('Politics', 'Politico',          'https://www.politico.com/rss/politics08.xml'),
        ('Politics', 'The Hill',          'https://thehill.com/feed/'),
        ('Politics', 'NPR Politics',      'https://feeds.npr.org/1014/rss.xml'),
        ('Politics', 'Roll Call',         'https://rollcall.com/feed/'),
        ('Politics', 'Axios',             'https://api.axios.com/feed/'),

        -- ── Space (5 feeds) ───────────────────────────────────────────────
        -- Space.com, NASA, SpaceNews, Planetary Society, NASASpaceFlight
        ('Space', 'Space.com',               'https://www.space.com/feeds/all'),
        ('Space', 'NASA Breaking News',      'https://www.nasa.gov/rss/dyn/breaking_news.rss'),
        ('Space', 'SpaceNews',              'https://spacenews.com/feed/'),
        ('Space', 'The Planetary Society',  'https://www.planetary.org/articles/rss'),
        ('Space', 'NASASpaceFlight',        'https://www.nasaspaceflight.com/feed/'),

        -- ── Education (5 feeds) ───────────────────────────────────────────
        -- Inside Higher Ed, EdSurge, Hechinger Report, The 74, EdWeek
        ('Education', 'Inside Higher Ed',  'https://www.insidehighered.com/rss.xml'),
        ('Education', 'EdSurge',           'https://www.edsurge.com/news.rss'),
        ('Education', 'Hechinger Report',  'https://hechingerreport.org/feed/'),
        ('Education', 'The 74',            'https://www.the74million.org/feed/'),
        ('Education', 'Education Week',    'https://www.edweek.org/feed/'),

        -- ── Labor (5 feeds) ───────────────────────────────────────────────
        -- HR Dive, EPI Blog, Labor Notes, Workforce, WorkLife
        ('Labor', 'HR Dive',                  'https://www.hrdive.com/feeds/news/'),
        ('Labor', 'Economic Policy Institute', 'https://www.epi.org/blog/feed/'),
        ('Labor', 'Labor Notes',              'https://labornotes.org/feed'),
        ('Labor', 'Workforce',                'https://www.workforce.com/feed/'),
        ('Labor', 'Fast Company Work Life',   'https://www.fastcompany.com/work-life/rss'),

        -- ── Sports (5 feeds) ──────────────────────────────────────────────
        -- ESPN, CBS Sports, Bleacher Report, The Athletic (limited), AP Sports
        ('Sports', 'ESPN',             'https://www.espn.com/espn/rss/news'),
        ('Sports', 'CBS Sports',       'https://www.cbssports.com/rss/headlines/'),
        ('Sports', 'Bleacher Report',  'https://bleacherreport.com/articles/feed?tag=all-sports'),
        ('Sports', 'Yahoo Sports',     'https://sports.yahoo.com/rss/'),
        ('Sports', 'NBC Sports',       'https://www.nbcsports.com/feed'),

        -- ── Entertainment (5 feeds) ───────────────────────────────────────
        -- Variety, Deadline, Hollywood Reporter, The Wrap, IndieWire
        ('Entertainment', 'Variety',              'https://variety.com/feed/'),
        ('Entertainment', 'Deadline',             'https://deadline.com/feed/'),
        ('Entertainment', 'Hollywood Reporter',   'https://www.hollywoodreporter.com/c/news/feed/'),
        ('Entertainment', 'The Wrap',             'https://www.thewrap.com/feed/'),
        ('Entertainment', 'IndieWire',            'https://www.indiewire.com/feed/'),

        -- ── Transportation (5 feeds) ──────────────────────────────────────
        -- Electrek (EVs), The Verge Transport, Transport Topics, FreightWaves, FlightGlobal
        ('Transportation', 'Electrek',             'https://electrek.co/feed/'),
        ('Transportation', 'The Verge Transport',  'https://www.theverge.com/transportation/rss/index.xml'),
        ('Transportation', 'Transport Topics',     'https://www.ttnews.com/rss.xml'),
        ('Transportation', 'FreightWaves',         'https://www.freightwaves.com/news/feed'),
        ('Transportation', 'FlightGlobal',         'https://www.flightglobal.com/rss')

) AS v(topic_name, name, feed_url) ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Verify
-- ─────────────────────────────────────────────────────────────────────────────
-- Expected: 20 topics total; 50 new sources (5 per new topic).
-- Run this query to confirm:
--
-- SELECT t.name, t.sort_order, t.is_active, COUNT(ns.id) AS source_count
-- FROM topics t
-- LEFT JOIN news_sources ns ON ns.topic_id = t.id AND ns.is_active = TRUE
-- GROUP BY t.id, t.name, t.sort_order, t.is_active
-- ORDER BY t.sort_order;
