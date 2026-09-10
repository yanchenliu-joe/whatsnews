"""
Cognitive briefing service (Phase 27).

Orchestrates:
  Phase 26 (narrative briefing) → cognitive enhancement pass.

Each narrative block gets 5 new cognitive fields:
  so_what, impact_level, risk_level, who_is_affected,
  action_implication, confidence.

No DB writes. No LLM calls. No pipeline changes.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.briefing.service import get_daily_briefing
from app.cognitive.builder import build_cognitive_block


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def get_daily_cognitive(
    topic: str,
    report_date: date | None = None,
    include_emerging: bool = True,
) -> dict:
    """
    Full cognitive intelligence briefing for one topic.

    Calls Phase 26 to get narrative blocks, then enhances each with
    cognitive scoring fields.

    Returns the same structure as /daily-briefing plus cognitive fields.
    """
    now = datetime.now(tz=ZoneInfo("UTC"))

    # ── Get Phase 26 narrative briefing ──────────────────────────────────────
    briefing = get_daily_briefing(
        topic,
        report_date=report_date,
        include_emerging=include_emerging,
    )

    if not briefing.get("available"):
        return {
            "topic": topic,
            "report_date": (report_date or now.date()).isoformat(),
            "available": False,
            "message": briefing.get("message", "No data available."),
        }

    start_ns = datetime.now(tz=ZoneInfo("UTC"))

    # ── Enhance primary narratives ────────────────────────────────────────────
    primary_cognitive = [
        build_cognitive_block(nb)
        for nb in briefing.get("briefing", [])
    ]

    # ── Enhance emerging signals (lighter pass) ───────────────────────────────
    emerging_cognitive = [
        build_cognitive_block(nb)
        for nb in briefing.get("emerging_signals", [])
    ]

    elapsed_ms = round(
        (datetime.now(tz=ZoneInfo("UTC")) - start_ns).total_seconds() * 1000, 1
    )

    _log(
        "cognitive_built",
        topic=topic,
        primary=len(primary_cognitive),
        emerging=len(emerging_cognitive),
        build_ms=elapsed_ms,
    )

    meta = briefing.get("meta", {})
    meta["cognitive_build_ms"] = elapsed_ms

    return {
        "topic":             briefing.get("topic", topic),
        "report_date":       briefing.get("report_date"),
        "available":         True,
        "briefing":          primary_cognitive,
        "emerging_signals":  emerging_cognitive,
        "threads":           briefing.get("threads", []),
        "meta":              meta,
    }
