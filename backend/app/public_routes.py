"""
Public (non-admin) routes: health check, article image lookup, device
registration, event tracking, topics list, and the legacy /daily-report
endpoint. /daily-report is no longer what the mobile client's main feed
calls (that's GET /feed, registered by app.feed.routes) but still works.
"""

from __future__ import annotations

import re
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
from fastapi import FastAPI, HTTPException, Request

from app.analytics.events import VALID_EVENT_NAMES, _record_event
from app.assembly import compute_importance_score
from app.database import get_connection
from app.log_utils import _log
from app.wim.batch import refine_single_with_ai
from app.wim.editorial_wim import generate_editorial_why_it_matters
from app.wim.service import fill_missing_why_it_matters as _fill_missing_why_it_matters

# Validates device-registration "HH:MM" notification_time strings.
_NOTIFICATION_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

# Used when DATABASE_URL is not configured (local dev without Supabase).
MOCK_REPORT = {
    "date": "2026-03-31",
    "topic": "Artificial Intelligence",
    "items": [
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
}


def enrich_item(item: dict, topic: str) -> dict:
    """
    Build the final article dict with why_it_matters.
    Pipeline: editorial rule draft → optional AI refinement.
    """
    draft = generate_editorial_why_it_matters(
        title=item["title"],
        summary=item.get("summary") or "",
        topic=topic,
        source=item.get("source") or "",
        editorial_metadata=item.get("editorial_metadata") or {},
    )
    outcome = refine_single_with_ai(
        draft["why_it_matters"],
        item["title"],
        item.get("summary") or "",
        topic,
        source=item.get("source") or "",
        editorial_metadata=item.get("editorial_metadata") or {},
    )
    return {**item, "why_it_matters": outcome.text}


def register_public_routes(app: FastAPI) -> None:
    """Attach the public (non-admin) endpoints."""

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    @app.post("/articles/images")
    async def articles_images(request: Request):
        """
        Given a list of article URLs, returns their image_url from the DB.
        Used by the mobile Saved screen to enrich existing saved articles.
        Body: {"urls": ["https://...", ...]}  (max 50)
        Response: {"images": {"url": "image_url_or_null", ...}}
        """
        try:
            body = await request.json()
        except Exception:
            return {"images": {}}
        urls = body.get("urls") or []
        if not isinstance(urls, list):
            return {"images": {}}
        from app.briefing_repository import get_image_urls_by_url
        try:
            conn = get_connection()
            result = get_image_urls_by_url(conn, [str(u) for u in urls if u])
            conn.close()
            return {"images": result}
        except Exception as e:
            _log("articles_images_error", error=str(e)[:120])
            return {"images": {}}

    @app.post("/devices")
    def register_device(body: dict):
        """
        Register (or update) a device push token, and optionally its preferred
        scheduled-push delivery time (Phase 34). Upsert — calling this again
        with the same push_token updates platform/notification_time/timezone to
        whatever was just sent (including clearing notification_time back to
        null), rather than being a no-op after the first call.
        """
        push_token = (body.get("push_token") or "").strip()
        if not push_token:
            raise HTTPException(status_code=422, detail="push_token is required")

        platform = (body.get("platform") or "").strip() or None

        notification_time = body.get("notification_time")
        if notification_time is not None:
            notification_time = str(notification_time).strip() or None
            if notification_time and not _NOTIFICATION_TIME_RE.match(notification_time):
                raise HTTPException(
                    status_code=422, detail="notification_time must be \"HH:MM\" or null"
                )

        timezone_name = body.get("timezone")
        if timezone_name is not None:
            timezone_name = str(timezone_name).strip() or None
            if timezone_name:
                try:
                    ZoneInfo(timezone_name)
                except Exception:
                    raise HTTPException(status_code=422, detail="timezone is not a valid IANA name")

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as exc:
            _log("internal_error_failed", error=str(exc))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_devices (push_token, platform, notification_time, timezone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (push_token) DO UPDATE SET
                    platform = EXCLUDED.platform,
                    notification_time = EXCLUDED.notification_time,
                    timezone = EXCLUDED.timezone
                """,
                (push_token, platform, notification_time, timezone_name),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        _log("device_registered", token_prefix=push_token[:12], notification_time=notification_time)
        return {"status": "ok"}

    @app.post("/events")
    def track_event(body: dict):
        """
        Record a lightweight product event (fire-and-forget from the client).
        Accepts: {event_name, article_id?, topic_name?, metadata_text?}
        """
        event_name = (body.get("event_name") or "").strip()
        if event_name not in VALID_EVENT_NAMES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown event_name. Valid: {', '.join(sorted(VALID_EVENT_NAMES))}",
            )

        _record_event(
            event_name=event_name,
            article_id=body.get("article_id"),
            topic_name=(body.get("topic_name") or "").strip() or None,
            metadata_text=(body.get("metadata_text") or "").strip() or None,
        )
        return {"status": "ok"}

    @app.get("/topics")
    def get_topics():
        """
        Returns all active topics, ordered by sort_order then name.
        Public endpoint — no authentication required.
        Falls back to a static list when DATABASE_URL is not configured.
        """
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error):
            return [
                {"id": 1, "name": "Artificial Intelligence", "sort_order": 0},
                {"id": 2, "name": "Climate Change", "sort_order": 1},
            ]

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, sort_order
                FROM topics
                WHERE is_active = TRUE
                ORDER BY sort_order ASC, name ASC
                """
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [
                {"id": r["id"], "name": r["name"], "sort_order": r["sort_order"]}
                for r in rows
            ]
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

    @app.get("/daily-report")
    def get_daily_report(topic: Optional[str] = None):
        """
        Return the most recent daily report.

        Primarily a read endpoint — articles should already be prepared via
        POST /admin/generate-report before this is called.

        - No param:       returns the report for the most recently updated topic.
        - ?topic=<name>:  returns the report for that specific topic.
                          Returns 404 if the topic does not exist in the database.
        """
        # No DATABASE_URL — use mock data for local dev without Supabase.
        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error):
            mock_topic = MOCK_REPORT["topic"]
            return {
                **MOCK_REPORT,
                "items": [enrich_item(item, mock_topic) for item in MOCK_REPORT["items"]],
            }

        # DATABASE_URL is set — surface real errors from here on.
        try:
            cur = conn.cursor()

            # Step 1: Resolve which topic to use.
            if topic:
                cur.execute("SELECT id, name, is_active FROM topics WHERE name = %s", (topic,))
                topic_row = cur.fetchone()
                if not topic_row:
                    cur.close()
                    conn.close()
                    raise HTTPException(
                        status_code=404,
                        detail=f"Topic '{topic}' not found.",
                    )
                if not topic_row["is_active"]:
                    cur.close()
                    conn.close()
                    raise HTTPException(
                        status_code=404,
                        detail=f"Topic '{topic}' is not available.",
                    )
            else:
                cur.execute(
                    """
                    SELECT t.id, t.name
                    FROM topics t
                    JOIN daily_reports dr ON dr.topic_id = t.id
                    WHERE t.is_active = TRUE
                    ORDER BY dr.report_date DESC
                    LIMIT 1
                    """
                )
                topic_row = cur.fetchone()
                if not topic_row:
                    cur.close()
                    conn.close()
                    return MOCK_REPORT

            # Step 2: Find the most recent daily report for this topic.
            cur.execute(
                """
                SELECT id, report_date
                FROM daily_reports
                WHERE topic_id = %s
                ORDER BY report_date DESC
                LIMIT 1
                """,
                (topic_row["id"],),
            )
            report = cur.fetchone()

            if not report:
                cur.close()
                conn.close()
                mock_topic = MOCK_REPORT["topic"]
                return {
                    **MOCK_REPORT,
                    "items": [enrich_item(item, mock_topic) for item in MOCK_REPORT["items"]],
                }

            # Step 3: Fetch articles with their stored why_it_matters values.
            # Cap matches MAX_ARTICLES_PER_REPORT in assembly.py.
            cur.execute(
                """
                SELECT id, title, summary, body_text, source, url, why_it_matters,
                       published_at, editorial_metadata, image_url
                FROM articles
                WHERE report_id = %s
                ORDER BY id ASC
                LIMIT 10
                """,
                (report["id"],),
            )
            articles = [dict(row) for row in cur.fetchall()]

            # Step 4: Read prepared data. If any why_it_matters is still missing
            # (admin endpoint not yet called), fill them in as a safety fallback.
            topic_name = topic_row["name"]
            counts = _fill_missing_why_it_matters(cur, articles, topic_name)
            if counts["articles_generated"] > 0:
                conn.commit()

            cur.close()
            conn.close()

            # Step 5: Order by importance so the most significant items lead.
            articles.sort(
                key=lambda a: compute_importance_score(a["title"], a.get("summary") or "", topic_name),
                reverse=True,
            )

            return {
                "date": str(report["report_date"]),
                "topic": topic_name,
                "items": [
                    {
                        "title": a["title"],
                        "summary": a["summary"],
                        "body_text": a.get("body_text") or None,
                        "source": a["source"],
                        "url": a["url"],
                        "why_it_matters": a["why_it_matters"],
                        "published_at": a["published_at"].isoformat() if a.get("published_at") else None,
                        "image_url": a.get("image_url") or None,
                    }
                    for a in articles
                ],
            }

        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")
