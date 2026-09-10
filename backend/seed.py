"""
Seed script for local development and testing.

Run from the backend/ directory:
    python seed.py

Seeds two topics, each with:
- a daily report with 5 articles
- example RSS news sources

Safe to run multiple times — existing articles and sources are replaced/upserted.
"""

from app.database import get_connection

SEED_DATA = [
    {
        "topic": "Artificial Intelligence",
        "articles": [
            {
                "title": "OpenAI releases GPT-5 with improved reasoning",
                "summary": "OpenAI has launched GPT-5, featuring significantly improved logical reasoning and reduced hallucinations compared to its predecessor.",
                "source": "TechCrunch",
                "url": "https://techcrunch.com/openai-gpt5",
            },
            {
                "title": "Google DeepMind advances protein folding research",
                "summary": "DeepMind's latest AlphaFold update can now predict the structure of entire protein complexes, opening new doors in drug discovery.",
                "source": "Nature",
                "url": "https://nature.com/deepmind-alphafold",
            },
            {
                "title": "EU passes landmark AI liability legislation",
                "summary": "The European Union has officially passed new rules requiring AI companies to disclose training data and accept liability for harmful outputs.",
                "source": "Reuters",
                "url": "https://reuters.com/eu-ai-liability",
            },
            {
                "title": "Meta open-sources new multimodal AI model",
                "summary": "Meta has released a new open-source model capable of processing text, images, and audio simultaneously, challenging proprietary alternatives.",
                "source": "The Verge",
                "url": "https://theverge.com/meta-multimodal-model",
            },
            {
                "title": "AI coding assistants now used by 60% of developers",
                "summary": "A new Stack Overflow survey finds that AI coding tools have crossed the majority threshold among professional developers for the first time.",
                "source": "Stack Overflow Blog",
                "url": "https://stackoverflow.blog/ai-coding-survey-2026",
            },
        ],
    },
    {
        "topic": "Climate Change",
        "articles": [
            {
                "title": "Global temperatures hit record high for third consecutive year",
                "summary": "Scientists confirm 2025 was the hottest year on record, continuing a streak that has alarmed climate researchers worldwide.",
                "source": "BBC News",
                "url": "https://bbc.com/news/climate-record-temperatures",
            },
            {
                "title": "Solar energy capacity doubles ahead of 2030 targets",
                "summary": "New data shows global solar installations have doubled in two years, putting renewable energy ahead of most optimistic projections.",
                "source": "Financial Times",
                "url": "https://ft.com/solar-energy-capacity",
            },
            {
                "title": "Arctic sea ice reaches new seasonal low",
                "summary": "Satellite imagery shows Arctic sea ice coverage has dropped to its lowest recorded level for this time of year, raising concerns about feedback loops.",
                "source": "The Guardian",
                "url": "https://theguardian.com/arctic-sea-ice",
            },
            {
                "title": "Carbon capture startup secures $500M in funding",
                "summary": "A direct air capture company has raised a major funding round to scale technology that removes CO2 directly from the atmosphere.",
                "source": "Bloomberg",
                "url": "https://bloomberg.com/carbon-capture-funding",
            },
            {
                "title": "UN climate summit sets new emissions reduction targets",
                "summary": "Nations at the latest UN summit agreed to accelerated emissions reduction timelines, with enforcement mechanisms stronger than previous agreements.",
                "source": "Reuters",
                "url": "https://reuters.com/un-climate-summit",
            },
        ],
    },
]


SEED_SOURCES = {
    "Artificial Intelligence": [
        {
            "name": "TechCrunch AI",
            "source_type": "rss",
            "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        },
        {
            "name": "The Verge AI",
            "source_type": "rss",
            "feed_url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        },
        {
            "name": "MIT Technology Review AI",
            "source_type": "rss",
            "feed_url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        },
        {
            "name": "Wired AI",
            "source_type": "rss",
            "feed_url": "https://www.wired.com/feed/tag/ai/latest/rss",
        },
        {
            "name": "VentureBeat AI",
            "source_type": "rss",
            "feed_url": "https://venturebeat.com/category/ai/feed/",
        },
    ],
    "Climate Change": [
        {
            "name": "Carbon Brief",
            "source_type": "rss",
            "feed_url": "https://www.carbonbrief.org/feed/",
        },
        {
            "name": "The Guardian Climate",
            "source_type": "rss",
            "feed_url": "https://www.theguardian.com/environment/climate-crisis/rss",
        },
        {
            "name": "Reuters Climate",
            "source_type": "rss",
            "feed_url": "https://www.reuters.com/business/environment/rss",
        },
        {
            "name": "Inside Climate News",
            "source_type": "rss",
            "feed_url": "https://insideclimatenews.org/feed/",
        },
        {
            "name": "BBC Science & Environment",
            "source_type": "rss",
            "feed_url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        },
        {
            "name": "Yale Environment 360",
            "source_type": "rss",
            "feed_url": "https://e360.yale.edu/feed",
        },
        {
            "name": "Climate Home News",
            "source_type": "rss",
            "feed_url": "https://www.climatechangenews.com/feed/",
        },
    ],
}


def seed_news_sources(cur, topic_id: int, topic_name: str) -> None:
    sources = SEED_SOURCES.get(topic_name, [])
    if not sources:
        return

    cur.execute("DELETE FROM news_sources WHERE topic_id = %s", (topic_id,))
    for src in sources:
        cur.execute(
            """
            INSERT INTO news_sources (topic_id, name, source_type, feed_url, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (topic_id, src["name"], src["source_type"], src["feed_url"]),
        )
    print(f"  [{topic_name}] {len(sources)} news sources inserted")


def seed_topic(cur, topic_name: str, articles: list, sort_order: int = 0) -> None:
    # Upsert topic — creates it if missing, activates it if it exists.
    cur.execute(
        """
        INSERT INTO topics (name, is_active, sort_order)
        VALUES (%s, TRUE, %s)
        ON CONFLICT (name) DO UPDATE
            SET is_active  = TRUE,
                sort_order = EXCLUDED.sort_order
        """,
        (topic_name, sort_order),
    )
    cur.execute("SELECT id FROM topics WHERE name = %s", (topic_name,))
    topic_id: int = cur.fetchone()["id"]

    seed_news_sources(cur, topic_id, topic_name)

    # Insert daily report for today if it doesn't exist
    cur.execute(
        """
        INSERT INTO daily_reports (topic_id, report_date)
        VALUES (%s, CURRENT_DATE)
        ON CONFLICT (topic_id, report_date) DO NOTHING
        """,
        (topic_id,),
    )
    cur.execute(
        "SELECT id FROM daily_reports WHERE topic_id = %s AND report_date = CURRENT_DATE",
        (topic_id,),
    )
    report_id: int = cur.fetchone()["id"]

    # Replace articles for this report so re-running seed is safe
    cur.execute("DELETE FROM articles WHERE report_id = %s", (report_id,))
    for article in articles:
        cur.execute(
            """
            INSERT INTO articles (report_id, title, summary, source, url)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (report_id, article["title"], article["summary"], article["source"], article["url"]),
        )

    print(f"  [{topic_name}] report_id={report_id}, {len(articles)} articles inserted")


def seed() -> None:
    conn = get_connection()
    cur = conn.cursor()

    for idx, entry in enumerate(SEED_DATA):
        seed_topic(cur, entry["topic"], entry["articles"], sort_order=idx)

    conn.commit()
    cur.close()
    conn.close()
    print("Done. Database seeded successfully.")


if __name__ == "__main__":
    seed()
