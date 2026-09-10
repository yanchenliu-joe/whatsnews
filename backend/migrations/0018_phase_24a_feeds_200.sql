-- Phase 24.1A: RSS feed expansion — ~100 → ~200 sources
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
--
-- Adds 5 additional feeds per topic across all 20 active topics (100 total).
-- Every feed is publicly accessible RSS/Atom with no known paywalls.
-- All guarded by NOT EXISTS on (topic_id, feed_url).

INSERT INTO news_sources (topic_id, name, feed_url, source_type, is_active)
SELECT t.id, v.name, v.feed_url, 'rss', TRUE
FROM topics t
JOIN (
    VALUES

    -- ── Artificial Intelligence (+5) ────────────────────────────────────────
    ('Artificial Intelligence', 'VentureBeat AI',       'https://venturebeat.com/category/ai/feed/'),
    ('Artificial Intelligence', 'MIT Technology Review', 'https://www.technologyreview.com/feed/'),
    ('Artificial Intelligence', 'ZDNet AI',              'https://www.zdnet.com/topic/artificial-intelligence/rss.xml'),
    ('Artificial Intelligence', 'InfoQ AI/ML',           'https://feed.infoq.com/ai-ml-data-eng/'),
    ('Artificial Intelligence', 'The Next Web Tech',     'https://thenextweb.com/feed/'),

    -- ── Climate Change (+5) ─────────────────────────────────────────────────
    ('Climate Change', 'Grist',                'https://grist.org/feed/'),
    ('Climate Change', 'Carbon Brief',         'https://www.carbonbrief.org/feed'),
    ('Climate Change', 'Yale E360',            'https://e360.yale.edu/feed.xml'),
    ('Climate Change', 'Mongabay',             'https://news.mongabay.com/feed/'),
    ('Climate Change', 'InsideClimate News',   'https://insideclimatenews.org/feed/'),

    -- ── Technology (+5) ─────────────────────────────────────────────────────
    ('Technology', 'The Verge',      'https://www.theverge.com/rss/index.xml'),
    ('Technology', 'Engadget',       'https://www.engadget.com/rss.xml'),
    ('Technology', 'TechCrunch',     'https://techcrunch.com/feed/'),
    ('Technology', 'ZDNet',          'https://www.zdnet.com/news/rss.xml'),
    ('Technology', '9to5Mac',        'https://9to5mac.com/feed/'),

    -- ── Markets (+5) ────────────────────────────────────────────────────────
    ('Markets', 'AP Business News',     'https://apnews.com/rss/business'),
    ('Markets', 'Investopedia News',    'https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline'),
    ('Markets', 'Calculated Risk',      'https://www.calculatedriskblog.com/feeds/posts/default'),
    ('Markets', 'Kiplinger',            'https://www.kiplinger.com/rss/feeds/index.xml'),
    ('Markets', 'CNBC Economy',         'https://www.cnbc.com/id/20910258/device/rss/rss.html'),

    -- ── Geopolitics (+5) ────────────────────────────────────────────────────
    ('Geopolitics', 'AP World News',      'https://apnews.com/rss/world-news'),
    ('Geopolitics', 'Voice of America',   'https://www.voanews.com/api/zmpkiipp_rek'),
    ('Geopolitics', 'RFE/RL',             'https://www.rferl.org/api/ztqosovrupqiepq'),
    ('Geopolitics', 'Devex',              'https://www.devex.com/news/rss.xml'),
    ('Geopolitics', 'RAND News',          'https://www.rand.org/news/press.rss'),

    -- ── Healthcare (+5) ─────────────────────────────────────────────────────
    ('Healthcare', 'KFF Health News',      'https://kffhealthnews.org/feed/'),
    ('Healthcare', 'Endpoints News',       'https://endpts.com/feed/'),
    ('Healthcare', 'HealthLeaders',        'https://www.healthleadersmedia.com/rss.xml'),
    ('Healthcare', 'NEJM Catalyst',        'https://catalyst.nejm.org/feed/'),
    ('Healthcare', 'BioPharma Dive',       'https://www.biopharmadive.com/feeds/news/'),

    -- ── Energy (+5) ─────────────────────────────────────────────────────────
    ('Energy', 'PV Magazine',          'https://www.pv-magazine.com/feed/'),
    ('Energy', 'Clean Energy Wire',    'https://www.cleanenergywire.org/rss.xml'),
    ('Energy', 'Canary Media',         'https://www.canarymedia.com/feed'),
    ('Energy', 'Offshore Energy',      'https://www.offshore-energy.biz/feed/'),
    ('Energy', 'Power Magazine',       'https://www.powermag.com/feed/'),

    -- ── Cybersecurity (+5) ──────────────────────────────────────────────────
    ('Cybersecurity', 'SANS ISC',             'https://isc.sans.edu/rssfeed.xml'),
    ('Cybersecurity', 'Naked Security',       'https://nakedsecurity.sophos.com/feed/'),
    ('Cybersecurity', 'Graham Cluley',        'https://grahamcluley.com/feed/'),
    ('Cybersecurity', 'Wired Security',       'https://www.wired.com/feed/category/security/latest/rss'),
    ('Cybersecurity', 'Infosecurity Magazine','https://www.infosecurity-magazine.com/rss/news/'),

    -- ── Business (+5) ───────────────────────────────────────────────────────
    ('Business', 'Harvard Business Review', 'https://feeds.hbr.org/harvardbusiness'),
    ('Business', 'Fast Company',           'https://www.fastcompany.com/latest/rss'),
    ('Business', 'Entrepreneur',           'https://www.entrepreneur.com/latest.rss'),
    ('Business', 'CEO Magazine',           'https://www.theceomagazine.com/feed/'),
    ('Business', 'Quartz',                 'https://qz.com/rss'),

    -- ── Defense (+5) ────────────────────────────────────────────────────────
    ('Defense', 'Military Times',        'https://www.militarytimes.com/arc/outboundfeeds/rss/'),
    ('Defense', 'National Interest',     'https://nationalinterest.org/rss.xml'),
    ('Defense', 'Task and Purpose',      'https://taskandpurpose.com/feed/'),
    ('Defense', 'War on the Rocks',      'https://warontherocks.com/feed/'),
    ('Defense', '19FortyFive',           'https://www.19fortyfive.com/feed/'),

    -- ── Science (+5) ────────────────────────────────────────────────────────
    ('Science', 'Science Alert',          'https://www.sciencealert.com/feed'),
    ('Science', 'MIT News Research',      'https://news.mit.edu/rss/research'),
    ('Science', 'Ars Technica Science',   'https://feeds.arstechnica.com/arstechnica/science'),
    ('Science', 'The Guardian Science',   'https://www.theguardian.com/science/rss'),
    ('Science', 'Space Daily Science',    'https://www.spacedaily.com/SpaceDaily.xml'),

    -- ── Crypto (+5) ─────────────────────────────────────────────────────────
    ('Crypto', 'CryptoBriefing',  'https://cryptobriefing.com/feed/'),
    ('Crypto', 'AMBCrypto',       'https://ambcrypto.com/feed/'),
    ('Crypto', 'CoinGape',        'https://coingape.com/feed/'),
    ('Crypto', 'NewsBTC',         'https://www.newsbtc.com/feed/'),
    ('Crypto', 'CryptoSlate',     'https://cryptoslate.com/feed/'),

    -- ── Real Estate (+5) ────────────────────────────────────────────────────
    ('Real Estate', 'Globe St',          'https://www.globest.com/feed/'),
    ('Real Estate', 'NREI Online',       'https://www.nreionline.com/rss.xml'),
    ('Real Estate', 'RE Business Online','https://rebusinessonline.com/feed/'),
    ('Real Estate', 'Connect CRE',       'https://www.connectcre.com/feed/'),
    ('Real Estate', 'Calculated Risk Housing', 'https://www.calculatedriskblog.com/feeds/posts/default'),

    -- ── Politics (+5) ───────────────────────────────────────────────────────
    ('Politics', 'NBC News Politics',  'https://feeds.nbcnews.com/nbcnews/public/politics'),
    ('Politics', 'ABC News Politics',  'https://abcnews.go.com/politics?format=rss'),
    ('Politics', 'Vox',                'https://www.vox.com/rss/index.xml'),
    ('Politics', 'Ballotpedia News',   'https://ballotpedia.org/feeds/news.xml'),
    ('Politics', 'OpenSecrets',        'https://www.opensecrets.org/news/feed/'),

    -- ── Space (+5) ──────────────────────────────────────────────────────────
    ('Space', 'Spaceflight Now',     'https://spaceflightnow.com/feed/'),
    ('Space', 'Universe Today',      'https://www.universetoday.com/feed/'),
    ('Space', 'Sky & Telescope',     'https://skyandtelescope.org/feed/'),
    ('Space', 'Space Daily',         'https://www.spacedaily.com/SpaceDaily.xml'),
    ('Space', 'Space News Wire',     'https://spacenews.com/feed/'),

    -- ── Education (+5) ──────────────────────────────────────────────────────
    ('Education', 'Chalkbeat',         'https://www.chalkbeat.org/rss.xml'),
    ('Education', 'Brookings Education','https://www.brookings.edu/topic/education/feed/'),
    ('Education', 'eLearning Industry','https://elearningindustry.com/feed'),
    ('Education', 'Diverse Education', 'https://diverseeducation.com/feed/'),
    ('Education', 'Campus Technology', 'https://campustechnology.com/rss-feeds/rss/rss.aspx'),

    -- ── Labor (+5) ──────────────────────────────────────────────────────────
    ('Labor', 'SHRM',                  'https://www.shrm.org/rss.xml'),
    ('Labor', 'Gallup Work',           'https://news.gallup.com/rss.aspx'),
    ('Labor', 'MIT Sloan Mgmt Review', 'https://sloanreview.mit.edu/feed/'),
    ('Labor', 'People Management',     'https://www.peoplemanagement.co.uk/rss'),
    ('Labor', 'The Conversation Labor','https://theconversation.com/us/topics/labor-markets-and-employment-19/articles.atom'),

    -- ── Sports (+5) ─────────────────────────────────────────────────────────
    ('Sports', 'Sports Illustrated',   'https://www.si.com/rss/si_topstories.rss'),
    ('Sports', 'Deadspin',             'https://deadspin.com/rss'),
    ('Sports', 'Sportico',             'https://www.sportico.com/feed/'),
    ('Sports', 'Yahoo Sports',         'https://sports.yahoo.com/rss/'),
    ('Sports', 'Sports Business Journal', 'https://www.sportsbusinessjournal.com/rss.aspx'),

    -- ── Entertainment (+5) ──────────────────────────────────────────────────
    ('Entertainment', 'Entertainment Weekly', 'https://ew.com/feed/'),
    ('Entertainment', 'The AV Club',          'https://www.avclub.com/rss'),
    ('Entertainment', 'Collider',             'https://collider.com/feed/'),
    ('Entertainment', 'Screen Rant',          'https://screenrant.com/feed/'),
    ('Entertainment', 'Pitchfork',            'https://pitchfork.com/rss/news/feed.xml'),

    -- ── Transportation (+5) ─────────────────────────────────────────────────
    ('Transportation', 'Smart Cities Dive', 'https://www.smartcitiesdive.com/feeds/news/'),
    ('Transportation', 'Auto Blog',         'https://www.autoblog.com/rss.xml'),
    ('Transportation', 'Electrive',         'https://www.electrive.com/feed/'),
    ('Transportation', 'Airport Technology','https://www.airport-technology.com/feed/'),
    ('Transportation', 'Modern Shipper',    'https://modernshipper.com/feed/')

) AS v(topic_name, name, feed_url) ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);

-- Verify
-- SELECT t.name, COUNT(ns.id) AS source_count
-- FROM topics t
-- LEFT JOIN news_sources ns ON ns.topic_id = t.id AND ns.is_active = TRUE
-- GROUP BY t.name ORDER BY t.sort_order;
-- Expected: each topic ~10 feeds, total ~200.
