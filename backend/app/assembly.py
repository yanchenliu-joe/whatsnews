"""
Report assembly service for WhatsNews.

Takes ingested candidate articles (topic_id set, report_id NULL) and assigns
the best ones to today's daily report for each topic.  This bridges the gap
between ingestion and the existing generation/read pipeline which operates
on report-linked articles.

This module is a standalone service layer — no endpoints, no scheduler
integration.  Call assemble_all_active_topics() to run a full assembly pass.

Usage (from backend/):
    python -m app.assembly
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.database import get_connection
from app.ingestion.config import article_scraping_enabled

MAX_ARTICLES_PER_REPORT = 10
MAX_PER_SOURCE = 2
FRESHNESS_WINDOW_DAYS = 4

# Title/summary substrings that mark non-briefing content.
QUALITY_EXCLUDE_PATTERNS = [
    "newsletter",       # email signup / promotional wrapper
    "opinion",          # subjective editorial, not factual briefing
    "editorial",        # same category as opinion
    "continue reading", # truncated teaser from paywalled feed
    "sign up",          # promotional call-to-action
    "subscribe",        # promotional call-to-action
    "cartoon",          # visual / non-article content
    "podcast",          # audio content reference
    "sponsored",        # paid / advertorial content
]

# Per-topic quality exclusions applied before relevance filtering.
TOPIC_QUALITY_EXCLUDE_PATTERNS: dict[str, list[str]] = {
    "Technology": [
        "favicon",
        "show hn",
        "ask hn",
    ],
    "Geopolitics": [
        "world cup",
        "football",
        "soccer",
        "sport",
        "sports",
        "olympics",
    ],
    "Healthcare": [
        "crossword",
        "recipe",
        "wellness tip",
        "fitness tip",
    ],
    "Energy": [
        "climate change",
        "carbon tax",
        "net zero pledge",
    ],
    "Business": [
        "federal reserve",
        "central bank",
        "interest rate",
        "inflation",
        "gdp",
        "recession",
        "treasury yield",
        "bond market",
        "cpi",
        "monetary policy",
        "rate cut",
        "rate hike",
        "wall street",
    ],
    "Defense": [
        "diplomacy",
        "diplomatic",
        "foreign minister",
        "embassy",
        "peace talks",
        "summit",
        "treaty",
        "humanitarian",
        "refugee",
        "migration",
        "election",
        "foreign policy",
    ],
    "Science": [
        "opinion",
        "politics",
        "election",
        "stock",
    ],
    "Crypto": [
        "stock market",
        "wall street",
        "federal reserve",
        "earnings",
    ],
    "Real Estate": [
        "stock",
        "bond",
        "crypto",
        "bitcoin",
    ],
    "Politics": [
        "sports",
        "entertainment",
        "box office",
        "album",
    ],
    "Sports": [
        "stock",
        "crypto",
        "bitcoin",
        "merger",
        "earnings",
    ],
    "Entertainment": [
        "stock",
        "crypto",
        "defense",
        "military",
        "election",
    ],
}

# Per-topic keywords for relevance filtering.
# An article must match at least one keyword to be considered relevant.
# Topics not listed here pass all articles (safe default for new topics).
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Artificial Intelligence": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural network", "gpt", "llm", "large language model",
        "openai", "deepmind", "anthropic", "chatbot", "generative",
        "automation", "algorithm", "training data", "model",
    ],
    "Climate Change": [
        "climate", "carbon", "emissions", "greenhouse", "warming",
        "renewable", "solar", "wind energy", "fossil fuel",
        "sustainability", "environment", "sea level", "drought",
        "deforestation", "biodiversity", "net zero", "clean energy",
        "heatwave", "extreme heat", "wildfire", "ecosystem",
        "microplastic", "microplastics", "pollution", "species",
        "habitat", "conservation", "forest", "ocean", "marine",
    ],
    "Technology": [
        "software", "hardware", "chips", "semiconductor", "cloud",
        "cybersecurity", "data center", "startup", "venture",
        "apple", "google", "microsoft", "amazon", "meta", "nvidia",
    ],
    "Markets": [
        "stocks", "bonds", "yields", "fed", "inflation", "rates",
        "earnings", "economy", "recession", "dollar", "oil", "gold",
        "bitcoin", "crypto", "wall street", "treasury",
    ],
    "Geopolitics": [
        "china", "russia", "ukraine", "taiwan", "middle east", "nato",
        "war", "defense", "sanctions", "diplomacy", "election", "military",
        "israel", "iran", "trade", "security",
        "migration", "migrant", "refugee", "refugees", "humanitarian",
        "displaced", "displacement", "united nations", "diplomatic",
        "embassy", "government", "governments", "foreign minister",
        "crisis", "border", "international",
    ],
    "Healthcare": [
        "fda", "drug", "pharma", "pharmaceutical", "clinical trial",
        "hospital", "medicare", "medicaid", "biotech", "vaccine",
        "disease", "healthcare", "patient", "treatment", "therapy",
        "diagnosis", "medical", "physician", "surgeon", "cancer",
        "diabetes", "alzheimer", "antibiotic", "prescription", "insurance",
    ],
    "Energy": [
        "oil", "gas", "opec", "pipeline", "lng", "refinery", "utility",
        "grid", "nuclear", "coal", "petroleum", "drilling", "power plant",
        "electricity", "tariff", "crude", "barrel", "natural gas",
        "power generation", "energy sector", "offshore", "upstream",
        "downstream", "hydrogen", "solar farm", "wind farm",
    ],
    "Cybersecurity": [
        "breach", "ransomware", "hack", "hacker", "malware", "vulnerability",
        "cve", "phishing", "zero-day", "zero day", "cyberattack", "cyber attack",
        "apt", "encryption", "exploit", "patch", "cybersecurity", "infosec",
        "threat actor", "botnet", "ddos", "spyware", "backdoor", "cisa",
    ],
    "Business": [
        "company", "companies", "corporate", "ceo", "cfo", "executive",
        "merger", "acquisition", "m&a", "takeover", "buyout",
        "earnings", "revenue", "profit", "quarterly", "layoff", "layoffs",
        "ipo", "startup", "enterprise", "workforce", "headquarters",
        "retailer", "manufacturer", "shareholder", "board", "resigned", "appointed",
        "workplace", "employer", "brand", "store", "retail",
    ],
    "Defense": [
        "pentagon", "dod", "defense department", "military", "army", "navy",
        "air force", "marines", "weapon", "weapons", "missile", "fighter",
        "tank", "submarine", "drone", "uav", "contract", "contractor",
        "lockheed", "raytheon", "northrop", "boeing", "general dynamics",
        "procurement", "defense budget", "appropriations", "ndaa",
        "hypersonic", "artillery", "munitions", "radar", "satellite",
        "f-35", "f-16", "destroyer", "carrier", "armament", "defense industry",
    ],

    # ── Phase 19 new topics ────────────────────────────────────────────────

    "Science": [
        "research", "study", "discovery", "scientists", "experiment",
        "journal", "nature", "cell", "science", "physics", "biology",
        "chemistry", "genetics", "genome", "dna", "rna", "protein",
        "neuroscience", "brain", "particle", "quantum", "telescope",
        "fossil", "evolution", "species", "lab", "laboratory", "findings",
        "breakthrough", "published", "peer-reviewed",
    ],
    "Crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
        "blockchain", "defi", "nft", "stablecoin", "usdt", "usdc",
        "web3", "token", "mining", "wallet", "exchange", "coinbase",
        "binance", "sec crypto", "crypto regulation", "digital asset",
        "altcoin", "solana", "ripple", "xrp", "ether", "layer 2",
        "smart contract", "dao", "yield farming",
    ],
    "Real Estate": [
        "housing", "mortgage", "home prices", "real estate", "property",
        "commercial real estate", "office space", "rent", "rental",
        "landlord", "tenant", "eviction", "zoning", "construction",
        "developer", "reits", "homebuyer", "first-time buyer",
        "foreclosure", "apartment", "condo", "residential", "housing market",
        "home sales", "inventory", "proptech", "interest rate mortgage",
    ],
    "Politics": [
        "congress", "senate", "house representatives", "white house",
        "president", "governor", "legislation", "bill", "vote", "election",
        "democrat", "republican", "gop", "bipartisan", "filibuster",
        "supreme court", "federal court", "administration", "cabinet",
        "policy", "campaign", "polling", "primary", "midterm",
        "executive order", "veto", "amendment", "lawmaker",
    ],
    "Space": [
        "nasa", "spacex", "rocket", "launch", "orbit", "satellite",
        "iss", "international space station", "mars", "moon", "lunar",
        "asteroid", "comet", "telescope", "james webb", "hubble",
        "astronaut", "cosmonaut", "spacecraft", "rover", "mission",
        "space station", "starship", "falcon", "artemis", "crew",
        "exoplanet", "galaxy", "black hole", "supernova", "astronomy",
        "space agency", "esa", "jaxa", "blue origin",
    ],
    "Education": [
        "school", "university", "college", "student", "tuition",
        "student loan", "higher education", "k-12", "teacher", "campus",
        "curriculum", "edtech", "learning", "enrollment", "graduation",
        "academic", "faculty", "dean", "chancellor", "accreditation",
        "charter school", "public school", "scholarship", "financial aid",
        "classroom", "literacy", "standardized test", "stem education",
    ],
    "Labor": [
        "workers", "union", "strike", "wage", "salary", "layoff",
        "unemployment", "jobs report", "hiring", "workforce", "labor market",
        "minimum wage", "collective bargaining", "nlrb", "labor board",
        "remote work", "hybrid", "gig economy", "freelance", "contractor",
        "hr", "human resources", "benefits", "pension", "severance",
        "pay gap", "equal pay", "labor shortage", "quit rate",
    ],
    "Sports": [
        "nfl", "nba", "mlb", "nhl", "mls", "ncaa", "super bowl",
        "playoff", "championship", "draft", "trade", "coach", "roster",
        "quarterback", "touchdown", "home run", "goal", "points",
        "standings", "tournament", "olympic", "world cup", "athlete",
        "contract", "signing", "injury", "comeback", "record",
        "espn", "sports", "game", "match", "season",
    ],
    "Entertainment": [
        "movie", "film", "box office", "streaming", "netflix", "hbo",
        "disney", "amazon prime", "apple tv", "hulu", "series", "show",
        "season", "episode", "actor", "actress", "director", "studio",
        "oscar", "emmy", "grammy", "award", "music", "album", "artist",
        "concert", "tour", "ticket", "celebrity", "hollywood",
        "paramount", "universal", "sony pictures", "warner bros",
    ],
    "Transportation": [
        "electric vehicle", "ev", "tesla", "autonomous", "self-driving",
        "aviation", "airline", "airport", "faa", "flight", "aircraft",
        "trucking", "freight", "logistics", "shipping", "cargo",
        "infrastructure", "highway", "transit", "rail", "amtrak",
        "uber", "lyft", "rideshare", "port", "supply chain",
        "fleet", "battery", "charging station", "vehicle recall",
    ],
}


# Generic keyword signals for importance scoring (fallback for unknown topics).
IMPORTANCE_KEYWORDS: dict[int, list[str]] = {
    3: [  # Regulation / policy
        "law", "regulation", "policy", "ban", "government",
        "legislation", "mandate", "executive order", "compliance",
        "directive", "enforce",
    ],
    2: [  # Funding / business
        "funding", "ipo", "billion", "million", "investment",
        "acquisition", "raises", "secures", "valuation", "merger",
    ],
    1: [  # Product / launch
        "launches", "releases", "announces", "unveils", "introduces",
        "new product", "new tool", "new feature", "ships", "debuts",
    ],
}

# Per-topic keyword tiers.  When a topic is listed here, its dict fully
# replaces the generic IMPORTANCE_KEYWORDS for scoring that topic's articles.
TOPIC_IMPORTANCE_KEYWORDS: dict[str, dict[int, list[str]]] = {
    "Artificial Intelligence": {
        3: [  # Governance / safety incidents — reshapes the whole field
            "regulation", "law", "policy", "ban", "government", "legislation",
            "breach", "hack", "security", "vulnerability", "safety",
            "ceo", "fired", "resigned", "leadership",
        ],
        2: [  # Major funding or launches — concrete market moves
            "funding", "billion", "investment", "acquisition", "ipo", "valuation",
            "launches", "releases", "open-source", "open source",
            "partnership", "deal", "merger",
        ],
        1: [  # Announcements / incremental signals
            "announces", "unveils", "introduces", "new feature", "api",
            "benchmark", "performance", "new model",
        ],
    },
    "Climate Change": {
        3: [  # Extreme weather / emissions policy — physical + regulatory urgency
            "regulation", "law", "policy", "ban", "government", "legislation",
            "hurricane", "wildfire", "flood", "drought", "heat wave", "heatwave",
            "extreme heat", "extreme weather", "emissions", "record temperature",
            "record high", "pollution", "microplastic",
        ],
        2: [  # Energy transition / infrastructure — structural shifts
            "renewable", "solar", "wind", "battery", "grid", "infrastructure",
            "transition", "electric vehicle",
            "sea level", "ice sheet", "glacier", "adaptation",
            "ecosystem", "biodiversity", "habitat", "conservation", "marine", "ocean",
        ],
        1: [  # Funding / research / pledges — important but less immediate
            "funding", "investment", "billion", "pledge", "commitment",
            "study", "research", "report", "findings",
        ],
    },
    "Technology": {
        3: [  # Security incidents and major regulatory action
            "breach", "hack", "antitrust", "ban", "regulation", "vulnerability",
        ],
        2: [  # Major corporate moves and product launches
            "acquisition", "merger", "ipo", "billion", "funding",
            "launches", "partnership",
        ],
        1: [  # Incremental product and platform updates
            "announces", "unveils", "releases", "update", "app",
        ],
    },
    "Markets": {
        3: [  # Macro shocks and systemic risk
            "recession", "crash", "default", "bankruptcy", "rate hike",
            "inflation", "fed",
        ],
        2: [  # Corporate and market-moving events
            "earnings", "ipo", "merger", "acquisition", "billion", "tariff",
        ],
        1: [  # Routine market updates
            "forecast", "dividend", "shares", "report", "announces",
        ],
    },
    "Geopolitics": {
        3: [  # Active conflict and major escalation
            "war", "invasion", "missile", "sanctions", "nuclear", "coup",
            "conflict", "refugee", "refugees", "humanitarian", "displacement",
        ],
        2: [  # Diplomatic shifts and high-stakes negotiations
            "summit", "treaty", "diplomacy", "nato", "ceasefire", "election",
            "migration", "migrant", "united nations", "border", "crisis",
        ],
        1: [  # Diplomatic process and deployments
            "talks", "minister", "deploys", "agreement", "announces",
            "embassy", "diplomatic", "foreign minister", "international",
        ],
    },
    "Healthcare": {
        3: [  # Regulatory action and public-health emergencies
            "fda", "approval", "recall", "outbreak", "pandemic", "ban",
            "emergency", "shortage", "contamination",
        ],
        2: [  # Clinical and corporate milestones
            "trial", "acquisition", "billion", "merger", "breakthrough",
            "phase 3", "phase iii", "approved",
        ],
        1: [  # Research and routine announcements
            "study", "research", "announces", "findings", "report",
        ],
    },
    "Energy": {
        3: [  # Supply shocks and geopolitical energy events
            "opec", "sanctions", "outage", "explosion", "embargo", "shortage",
            "pipeline leak", "refinery fire", "blackout",
        ],
        2: [  # Production and infrastructure moves
            "production", "refinery", "pipeline", "deal", "acquisition",
            "lng", "drilling", "capacity", "export",
        ],
        1: [  # Market updates and forecasts
            "forecast", "prices", "report", "barrel", "inventory",
        ],
    },
    "Cybersecurity": {
        3: [  # Active incidents and critical threats
            "breach", "ransomware", "zero-day", "zero day", "critical",
            "nation-state", "nation state", "cisa", "exploit",
        ],
        2: [  # Remediation and enforcement
            "patch", "fine", "lawsuit", "million records", "exposed",
            "stolen", "leaked", "vulnerability",
        ],
        1: [  # Advisories and discoveries
            "warns", "advisory", "discovered", "alert", "report",
        ],
    },
    "Business": {
        3: [  # Leadership crises and regulatory action
            "ceo", "fired", "resigned", "bankruptcy", "layoff", "layoffs",
            "antitrust", "sec", "lawsuit", "recall", "fraud",
        ],
        2: [  # M&A and major corporate moves
            "merger", "acquisition", "ipo", "billion", "earnings",
            "takeover", "buyout", "deal",
        ],
        1: [  # Routine corporate announcements
            "announces", "appoints", "partnership", "expansion", "opens", "launch",
        ],
    },
    "Defense": {
        3: [  # Contracts, budgets, and major deployments
            "contract", "award", "procurement", "ndaa", "budget",
            "deployment", "weapons", "hypersonic", "appropriations",
        ],
        2: [  # Program milestones and production
            "billion", "program", "acquisition", "delivery", "production",
            "upgrade", "ship", "deliver",
        ],
        1: [  # Tests and announcements
            "announces", "unveils", "test", "demonstration", "report",
        ],
    },
}


def compute_importance_score(title: str, summary: str, topic: str = "") -> int:
    """
    Score an article's importance using keyword signals in title + summary.
    Returns 3, 2, 1, or 0 (general).  First matching tier wins.

    When topic is provided and has custom keywords, those are used instead
    of the generic fallback.
    """
    keywords = TOPIC_IMPORTANCE_KEYWORDS.get(topic, IMPORTANCE_KEYWORDS)
    text = (title + " " + (summary or "")).lower()
    for score in (3, 2, 1):
        if score in keywords and any(kw in text for kw in keywords[score]):
            return score
    return 0


def compute_fallback_score(
    title: str,
    summary: str,
    topic_name: str,
    effective_date,
) -> float:
    """
    Normalized score for fallback article selection.

    Each factor is bounded to [0, 1] and combined with fixed weights so that no
    single factor can dominate and rankings are deterministic across runs:

        score = 0.5 * keyword_score
              + 0.3 * importance_score
              + 0.2 * recency_score

    keyword_score  — fraction of topic keywords found in title+summary.
                     0.5 when the topic has no keyword list (neutral).
    importance_score — importance tier (0-3) divided by 3.
    recency_score  — linear decay from 1.0 (today) to 0.0 at 30 days.
    """
    text = (title + " " + (summary or "")).lower()

    keywords = TOPIC_KEYWORDS.get(topic_name, [])
    if keywords:
        keyword_hits = sum(1 for kw in keywords if kw in text)
        keyword_score = min(1.0, keyword_hits / len(keywords))
    else:
        keyword_score = 0.5  # neutral when topic has no keyword list

    importance_raw = compute_importance_score(title, summary, topic_name)
    importance_score = importance_raw / 3.0  # max raw value is 3

    recency_score = 0.0
    if effective_date:
        try:
            now = datetime.now(tz=ZoneInfo("UTC"))
            age_days = (now - effective_date).total_seconds() / 86400
            recency_score = max(0.0, 1.0 - age_days / 30.0)
        except Exception:
            pass

    return 0.5 * keyword_score + 0.3 * importance_score + 0.2 * recency_score


# ── Quality filtering ─────────────────────────────────────────────────────────

def passes_quality_filter(title: str, summary: str) -> bool:
    """Return False if the article matches any low-signal pattern."""
    text = (title + " " + (summary or "")).lower()
    return not any(p in text for p in QUALITY_EXCLUDE_PATTERNS)


def passes_topic_quality_filter(title: str, summary: str, topic_name: str) -> bool:
    """Return False if the article matches a topic-specific low-signal pattern."""
    patterns = TOPIC_QUALITY_EXCLUDE_PATTERNS.get(topic_name)
    if not patterns:
        return True
    text = (title + " " + (summary or "")).lower()
    return not any(p in text for p in patterns)


def passes_relevance_filter(title: str, summary: str, topic_name: str) -> bool:
    """
    Return False if the article does not match any keyword for its topic.
    Topics without a keyword list pass all articles.
    """
    keywords = TOPIC_KEYWORDS.get(topic_name)
    if keywords is None:
        return True
    text = (title + " " + (summary or "")).lower()
    return any(kw in text for kw in keywords)


def select_with_source_diversity(
    candidates: list[dict],
    limit: int,
    max_per_source: int = MAX_PER_SOURCE,
) -> list[dict]:
    """
    Pick up to `limit` candidates, capping each source at `max_per_source`.
    Preserves input ordering (candidates should be pre-sorted by recency).
    """
    selected: list[dict] = []
    source_counts: dict[str, int] = {}

    for c in candidates:
        if len(selected) >= limit:
            break
        src = c.get("source", "")
        count = source_counts.get(src, 0)
        if count >= max_per_source:
            continue
        selected.append(c)
        source_counts[src] = count + 1

    return selected


# ── Logging (matches main.py / ingestion.py convention) ───────────────────────

def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


# ── Database helpers ──────────────────────────────────────────────────────────

def ensure_daily_report(cur, topic_id: int) -> tuple[int, date]:
    """
    Create today's daily_report for a topic if it doesn't exist yet.
    Returns (report_id, report_date).
    """
    cur.execute(
        """
        INSERT INTO daily_reports (topic_id, report_date)
        VALUES (%s, CURRENT_DATE)
        ON CONFLICT (topic_id, report_date) DO NOTHING
        """,
        (topic_id,),
    )
    cur.execute(
        "SELECT id, report_date FROM daily_reports WHERE topic_id = %s AND report_date = CURRENT_DATE",
        (topic_id,),
    )
    row = cur.fetchone()
    return row["id"], row["report_date"]


def count_report_articles(cur, report_id: int) -> int:
    """Count how many articles are already assigned to a report."""
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM articles WHERE report_id = %s",
        (report_id,),
    )
    return cur.fetchone()["cnt"]


def clear_report_articles(cur, report_id: int) -> int:
    """
    Unlink all articles currently assigned to a report by setting
    report_id = NULL.  Returns the number of articles cleared.
    This puts them back into the candidate pool for re-selection.
    Existing why_it_matters text is preserved on the article row so
    re-selected articles skip unnecessary regeneration.
    """
    cur.execute(
        "UPDATE articles SET report_id = NULL WHERE report_id = %s",
        (report_id,),
    )
    return cur.rowcount


def load_candidates(cur, topic_id: int, limit: int) -> list[dict]:
    """
    Load unassigned ingested articles for a topic.

    Ordering: published_at (real publish date) is preferred, falling back to
    fetched_at for articles where the feed didn't provide a date.

    Freshness: articles from the last FRESHNESS_WINDOW_DAYS days are preferred.
    If too few fresh candidates survive quality filtering, older articles fill
    the remaining slots so reports are never empty.
    """
    pool_size = max(limit * 4, 20)
    cur.execute(
        """
        SELECT id, title,
               COALESCE(summary, '') AS summary,
               COALESCE(source, '')  AS source,
               body_text,
               COALESCE(published_at, fetched_at) AS effective_date
        FROM articles
        WHERE topic_id = %s
          AND report_id IS NULL
        ORDER BY COALESCE(published_at, fetched_at) DESC NULLS LAST, id DESC
        LIMIT %s
        """,
        (topic_id, pool_size),
    )
    rows = [dict(r) for r in cur.fetchall()]
    filtered = [r for r in rows if passes_quality_filter(r["title"], r["summary"])]

    cutoff = datetime.now(tz=ZoneInfo("UTC")) - timedelta(days=FRESHNESS_WINDOW_DAYS)
    fresh = [r for r in filtered if r.get("effective_date") and r["effective_date"] >= cutoff]
    stale = [r for r in filtered if not r.get("effective_date") or r["effective_date"] < cutoff]

    return (fresh + stale)[:limit]


def assign_articles_to_report(cur, article_ids: list[int], report_id: int) -> int:
    """
    Set report_id on the given articles.  Returns number of rows updated.
    """
    if not article_ids:
        return 0
    cur.execute(
        "UPDATE articles SET report_id = %s WHERE id = ANY(%s)",
        (report_id, article_ids),
    )
    return cur.rowcount


# ── Per-topic assembly ────────────────────────────────────────────────────────

def assemble_report_for_topic(
    conn,
    topic_id: int,
    topic_name: str,
    max_articles: int = MAX_ARTICLES_PER_REPORT,
) -> dict:
    """
    Assemble today's report for a single topic:
    1. Ensure today's daily_report exists.
    2. Clear any previously assigned articles (rebuild from scratch).
    3. Load quality-filtered candidates from the full pool.
    4. Apply topic-specific quality exclusions (before relevance filtering).
    5. Split into strict (keyword-matched) and relaxed (quality-only) pools.
    6. Select from strict first, fill remaining slots from relaxed.
    7. Apply source diversity cap across both pools.
    8. Assign the top articles to the report.

    Each run produces a fresh selection reflecting the latest candidates
    and filtering logic.  Previously generated why_it_matters text is
    preserved on re-selected articles.

    Returns a stats dict.
    """
    cur = conn.cursor()

    report_id, report_date = ensure_daily_report(cur, topic_id)
    conn.commit()

    cleared = clear_report_articles(cur, report_id)
    conn.commit()
    if cleared:
        _log("assembly_report_cleared",
             topic=topic_name, report_id=report_id, cleared=cleared)

    pool = load_candidates(cur, topic_id, limit=max_articles * 3)

    quality_pool = []
    for c in pool:
        if passes_topic_quality_filter(c["title"], c["summary"], topic_name):
            quality_pool.append(c)
        else:
            _log("assembly_quality_excluded", topic=topic_name, title=c["title"])
    pool = quality_pool

    # Content gate: when scraping is enabled, exclude articles with no scraped
    # body text — these are paywalled or bot-blocked sources that would only
    # show a short RSS snippet, providing no reading value.
    # If ALL candidates are paywalled, fall back to summary-only rather than
    # producing an empty report.
    if article_scraping_enabled():
        _MIN_BODY_LEN = 300
        pre_gate = len(pool)
        gated = [
            c for c in pool
            if c.get("body_text") and len(c["body_text"]) >= _MIN_BODY_LEN
        ]
        excluded = pre_gate - len(gated)
        if excluded:
            _log(
                "assembly_content_gate_excluded",
                topic=topic_name,
                excluded=excluded,
                remaining=len(gated),
            )
        if gated:
            pool = gated
        else:
            # All candidates failed the content gate (all paywalled / blocked).
            # Keep the quality_pool so the report isn't empty — articles will
            # show summary text only.
            _log(
                "assembly_content_gate_fallback",
                topic=topic_name,
                reason="all_paywalled",
                candidates=pre_gate,
            )

    strict = [c for c in pool if passes_relevance_filter(
        c["title"], c["summary"], topic_name)]
    relaxed = [c for c in pool if not passes_relevance_filter(
        c["title"], c["summary"], topic_name)]

    # Strict-first ordering: source diversity is applied across both pools,
    # so strict items are always preferred but relaxed items can fill gaps.
    combined = strict + relaxed
    selected = select_with_source_diversity(combined, limit=max_articles)

    strict_ids = {c["id"] for c in strict}
    from_strict = sum(1 for c in selected if c["id"] in strict_ids)
    from_relaxed = len(selected) - from_strict

    if relaxed and from_relaxed:
        _log("assembly_relevance_relaxed",
             topic=topic_name, strict=from_strict,
             relaxed=from_relaxed, strict_pool=len(strict),
             relaxed_pool=len(relaxed))
    elif len(pool) > len(strict):
        _log("assembly_relevance_filtered",
             topic=topic_name, pool=len(pool),
             strict=len(strict), dropped=len(relaxed))

    if not selected:
        # Emergency fallback: bypass all quality/relevance filters and use the
        # most recent available candidates so the report is never empty.
        pool_size = max(max_articles * 4, 20)
        cur.execute(
            """
            SELECT id, title,
                   COALESCE(summary, '') AS summary,
                   COALESCE(source, '')  AS source,
                   COALESCE(published_at, fetched_at) AS effective_date
            FROM articles
            WHERE topic_id = %s
              AND report_id IS NULL
            ORDER BY COALESCE(published_at, fetched_at) DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            (topic_id, pool_size),
        )
        fallback_rows = [dict(r) for r in cur.fetchall()]
        if fallback_rows:
            # Rank by topic relevance + importance + recency rather than raw
            # chronological order so the fallback still prefers on-topic articles.
            fallback_rows.sort(
                key=lambda r: compute_fallback_score(
                    r["title"], r["summary"], topic_name, r.get("effective_date")
                ),
                reverse=True,
            )
            selected = select_with_source_diversity(fallback_rows, limit=max_articles)
            _log("assembly_fallback_used",
                 topic=topic_name, fallback_selected=len(selected))

    article_ids = [c["id"] for c in selected]
    assigned = assign_articles_to_report(cur, article_ids, report_id)
    conn.commit()

    _log("assembly_topic_done",
         topic=topic_name,
         report_id=report_id,
         report_date=report_date,
         pool=len(pool),
         strict=len(strict),
         selected=len(selected),
         from_strict=from_strict,
         from_relaxed=from_relaxed,
         assigned=assigned,
         cleared=cleared)

    cur.close()
    return {
        "topic": topic_name,
        "report_id": report_id,
        "report_date": str(report_date),
        "candidates_found": len(pool),
        "strict_pool": len(strict),
        "relaxed_pool": len(relaxed),
        "articles_assigned": assigned,
        "from_strict": from_strict,
        "from_relaxed": from_relaxed,
        "articles_cleared": cleared,
    }


# ── Full assembly pass ────────────────────────────────────────────────────────

def assemble_all_active_topics() -> dict:
    """
    Run report assembly for every active topic.
    Opens its own database connection, runs assembly, closes it.

    Returns aggregate stats.
    """
    _log("assembly_started")

    try:
        conn = get_connection()
    except ValueError as e:
        _log("assembly_aborted", reason=str(e))
        return {
            "topics_processed": 0,
            "total_candidates": 0,
            "total_assigned": 0,
            "errors_count": 1,
        }

    cur = conn.cursor()
    cur.execute(
        "SELECT id, name FROM topics WHERE is_active = TRUE ORDER BY sort_order ASC, name ASC"
    )
    topics = [dict(r) for r in cur.fetchall()]
    cur.close()

    totals = {
        "topics_processed": 0,
        "total_candidates": 0,
        "total_assigned": 0,
        "errors_count": 0,
        "per_topic": [],
    }

    for topic in topics:
        try:
            stats = assemble_report_for_topic(conn, topic["id"], topic["name"])
            totals["topics_processed"] += 1
            totals["total_candidates"] += stats["candidates_found"]
            totals["total_assigned"] += stats["articles_assigned"]
            totals["per_topic"].append(stats)
        except Exception as e:
            totals["errors_count"] += 1
            _log("assembly_topic_error", topic=topic["name"], error=str(e)[:200])

    conn.close()

    _log("assembly_completed",
         topics=totals["topics_processed"],
         assigned=totals["total_assigned"],
         errors=totals["errors_count"])

    return totals


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    result = assemble_all_active_topics()
    try:
        from app.pipeline.orchestrator import run_scheduled_preparation

        _log("assembly_generation_starting")
        run_scheduled_preparation()
        _log("assembly_generation_done")
        result["generation"] = {"status": "completed"}
    except Exception as e:
        _log("assembly_generation_failed", error=str(e)[:500])
        result["generation"] = {"status": "failed", "error": str(e)[:500]}

    print(json.dumps(result, indent=2))
