-- Phase 25: Feed expansion — add requested sources across topics
-- Run once in the Supabase SQL Editor. Safe to re-run (fully idempotent).
-- Guards every row with NOT EXISTS on (topic_id, feed_url).

INSERT INTO news_sources (topic_id, name, feed_url, source_type, is_active)
SELECT t.id, v.name, v.feed_url, 'rss', TRUE
FROM topics t
JOIN (
    VALUES

    -- ── Technology ───────────────────────────────────────────────────────────
    ('Technology', 'Wired',            'https://www.wired.com/feed/rss'),
    ('Technology', 'Mashable',         'https://mashable.com/feeds/rss/all'),
    ('Technology', 'Gizmodo',          'https://gizmodo.com/rss'),
    ('Technology', 'Daring Fireball',  'https://daringfireball.net/feeds/main'),
    ('Technology', 'CNET',             'https://www.cnet.com/rss/news/'),
    ('Technology', 'BGR',              'https://bgr.com/feed/'),

    -- ── Entertainment ────────────────────────────────────────────────────────
    ('Entertainment', 'Vanity Fair',         'https://www.vanityfair.com/feed/rss'),
    ('Entertainment', 'The New Yorker',      'https://www.newyorker.com/feed/everything'),
    ('Entertainment', 'Polygon',             'https://www.polygon.com/rss/index.xml'),
    ('Entertainment', 'PopCulture.com',      'https://popculture.com/feed/'),
    ('Entertainment', 'NME',                 'https://www.nme.com/feed'),
    ('Entertainment', 'Kotaku',              'https://kotaku.com/rss'),
    ('Entertainment', 'IGN',                 'https://feeds.ign.com/ign/all'),
    ('Entertainment', 'GQ',                  'https://www.gq.com/feed/rss'),
    ('Entertainment', 'Esquire',             'https://www.esquire.com/rss/all.xml'),
    ('Entertainment', 'Entertainment Tonight','https://www.etonline.com/feeds/rss/top_stories_1/'),
    ('Entertainment', 'BuzzFeed',            'https://www.buzzfeed.com/index.xml'),
    ('Entertainment', 'Serious Eats',        'https://www.seriouseats.com/feeds/all.xml'),
    -- Fashion / lifestyle
    ('Entertainment', 'HYPEBEAST',           'https://hypebeast.com/feed'),
    ('Entertainment', 'Who What Wear',       'https://www.whowhatwear.com/rss'),
    ('Entertainment', 'Spotted Fashion',     'https://www.spottedfashion.com/feed/'),
    ('Entertainment', 'Permanent Style',     'https://www.permanentstyle.com/feed'),
    ('Entertainment', 'Junior Style',        'https://www.juniorstyle.co.uk/feed/'),
    ('Entertainment', 'Fashion Network',     'https://us.fashionnetwork.com/rss/feeds.rss'),
    ('Entertainment', 'Glamour and Gains',   'https://glamourandgains.com/feed/'),

    -- ── Sports ───────────────────────────────────────────────────────────────
    ('Sports', 'Sporting News',      'https://www.sportingnews.com/rss'),
    ('Sports', 'Sky Sports',         'https://www.skysports.com/rss/12040'),
    ('Sports', 'New York Post Sports','https://nypost.com/sports/feed/'),
    ('Sports', 'MotorSport.com',     'https://www.motorsport.com/rss/f1/news/'),
    ('Sports', 'AutoSport',          'https://www.autosport.com/rss/'),

    -- ── Business ─────────────────────────────────────────────────────────────
    ('Business', 'Forbes',           'https://www.forbes.com/real-time/feed2/'),
    ('Business', 'Business Insider', 'https://feeds.businessinsider.com/custom/all'),
    ('Business', 'TIME Business',    'https://time.com/business/feed/'),
    ('Business', 'Seth''s Blog',     'https://seths.blog/feed/'),

    -- ── Geopolitics ──────────────────────────────────────────────────────────
    ('Geopolitics', 'Sky News',          'https://feeds.skynews.com/feeds/rss/world.xml'),
    ('Geopolitics', 'BBC News',          'http://feeds.bbci.co.uk/news/rss.xml'),
    ('Geopolitics', 'New York Post News','https://nypost.com/news/feed/'),
    ('Geopolitics', 'TIME World',        'https://time.com/world/feed/'),
    ('Geopolitics', 'NPR News',          'https://feeds.npr.org/1001/rss.xml'),

    -- ── Real Estate ──────────────────────────────────────────────────────────
    ('Real Estate', 'Dezeen',  'https://www.dezeen.com/feed/'),
    ('Real Estate', 'Dwell',   'https://www.dwell.com/rss'),

    -- ── Science ──────────────────────────────────────────────────────────────
    ('Science', 'Smithsonian Magazine', 'https://www.smithsonianmag.com/rss/newest_articles/')

) AS v(topic_name, name, feed_url)
ON t.name = v.topic_name
WHERE NOT EXISTS (
    SELECT 1 FROM news_sources ns
    WHERE ns.topic_id = t.id AND ns.feed_url = v.feed_url
);
