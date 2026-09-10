"""
Daily briefing service (Phase 26).

Orchestrates the full narrative intelligence pipeline:
  1. Get signal-scored events from Phase 25 intelligence layer
  2. Transform each event into a narrative block
  3. Apply cross-event thread synthesis
  4. Return structured briefing object

Performance target: <20ms per topic (in-process, no DB writes, no LLM).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.intelligence.service import get_daily_intelligence
from app.briefing.builder import build_narrative_block, extract_entities
from app.briefing.templates import THREAD_LABEL_TEMPLATE, THREAD_DEFAULT_LABEL

# Briefing tiers
_PRIMARY_MIN_SCORE  = 70   # high signal → main briefing
_EMERGING_MIN_SCORE = 40   # informational → emerging signals appendix
_MAX_PRIMARY        = 8    # cap on main narrative items
_MAX_EMERGING       = 5    # cap on emerging signal items
_THREAD_MIN_EVENTS  = 2    # minimum events to form a thread


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


# ── Thread detection ──────────────────────────────────────────────────────────

def _build_threads(primary_narratives: list[dict]) -> list[dict]:
    """
    Detect cross-event entity threads.

    A thread is formed when ≥2 primary narratives share a prominent named entity.
    Returns list of thread dicts sorted by involved_event_count DESC.
    """
    if len(primary_narratives) < _THREAD_MIN_EVENTS:
        return []

    # Build entity → event index
    entity_to_events: dict[str, list[int]] = {}
    for idx, narrative in enumerate(primary_narratives):
        texts = [
            narrative.get("headline", ""),
            narrative.get("what_happened", ""),
        ]
        for a in narrative.get("top_articles", []):
            texts.append(a.get("title", ""))

        for entity in extract_entities(texts):
            entity_to_events.setdefault(entity, []).append(idx)

    # Keep entities that appear in ≥2 events
    active = {
        entity: events
        for entity, events in entity_to_events.items()
        if len(events) >= _THREAD_MIN_EVENTS
    }

    if not active:
        return []

    # Merge overlapping entity groups into threads
    merged: list[set[str]] = []
    for entity, event_idxs in sorted(active.items(), key=lambda x: -len(x[1])):
        event_set = set(event_idxs)
        placed = False
        for group in merged:
            if event_set & group:
                group.update(event_set)
                placed = True
                break
        if not placed:
            merged.append(event_set)

    # Build thread output
    threads = []
    for event_idxs in merged:
        if len(event_idxs) < _THREAD_MIN_EVENTS:
            continue

        involved = sorted(event_idxs)
        # Find the dominant entity for this thread
        dominant_entity = None
        best_count = 0
        for entity, idxs in active.items():
            shared = len(set(idxs) & event_idxs)
            if shared > best_count:
                best_count = shared
                dominant_entity = entity

        label = (
            THREAD_LABEL_TEMPLATE.format(entity=dominant_entity)
            if dominant_entity
            else THREAD_DEFAULT_LABEL
        )

        threads.append({
            "thread_label": label,
            "entity": dominant_entity,
            "involved_event_count": len(involved),
            "event_headlines": [
                primary_narratives[i]["headline"]
                for i in involved
                if i < len(primary_narratives)
            ],
            "avg_signal_score": round(
                sum(primary_narratives[i]["signal_score"] for i in involved if i < len(primary_narratives))
                / max(1, len(involved)),
                1,
            ),
        })

    threads.sort(key=lambda t: t["involved_event_count"], reverse=True)
    return threads[:5]  # cap threads


# ── Main service ──────────────────────────────────────────────────────────────

def get_daily_briefing(
    topic: str,
    report_date: date | None = None,
    include_emerging: bool = True,
) -> dict:
    """
    Full narrative intelligence briefing for one topic.

    Calls the Phase 25 intelligence layer to get signal-scored events,
    then transforms them into structured narrative blocks.

    Noise (score < 40) is completely excluded.
    Primary (score ≥ 70): up to MAX_PRIMARY narrative items.
    Emerging (score 40–69): up to MAX_EMERGING items in appendix.
    """
    now = datetime.now(tz=ZoneInfo("UTC"))

    # ── Step 1: Get intelligence events ──────────────────────────────────────
    intel = get_daily_intelligence(topic, report_date=report_date)

    if not intel.get("available"):
        return {
            "topic": topic,
            "report_date": (report_date or now.date()).isoformat(),
            "available": False,
            "message": intel.get("message", "No data available."),
        }

    all_events = intel.get("events", [])  # already excludes noise tier

    if not all_events:
        return {
            "topic": intel.get("topic", topic),
            "report_date": intel.get("report_date"),
            "available": True,
            "briefing": [],
            "emerging_signals": [],
            "threads": [],
            "meta": {
                "total_events": 0,
                "noise_suppressed": intel.get("noise_suppressed_count", 0),
            },
        }

    # ── Step 2: Split by tier ─────────────────────────────────────────────────
    primary_events   = [e for e in all_events if e.get("signal_score", 0) >= _PRIMARY_MIN_SCORE]
    emerging_events  = [e for e in all_events if _EMERGING_MIN_SCORE <= e.get("signal_score", 0) < _PRIMARY_MIN_SCORE]

    # Apply ranking within each tier (signal_score → sources_count → recency)
    def _rank_key(e):
        pub = None
        articles = e.get("top_articles") or []
        if articles:
            pub = articles[0].get("published_at") or ""
        return (
            -e.get("signal_score", 0),
            -e.get("sources_count", 0),
            pub or "",
        )

    primary_events.sort(key=_rank_key)
    emerging_events.sort(key=_rank_key)

    # Cap
    primary_events  = primary_events[:_MAX_PRIMARY]
    emerging_events = emerging_events[:_MAX_EMERGING]

    # ── Step 3: Build narrative blocks ────────────────────────────────────────
    start_ns = datetime.now(tz=ZoneInfo("UTC"))

    primary_narratives = [build_narrative_block(e) for e in primary_events]
    emerging_narratives = [build_narrative_block(e) for e in emerging_events] if include_emerging else []

    elapsed_ms = round(
        (datetime.now(tz=ZoneInfo("UTC")) - start_ns).total_seconds() * 1000, 1
    )

    # ── Step 4: Cross-event thread detection ──────────────────────────────────
    threads = _build_threads(primary_narratives)

    signal_summary = intel.get("signal_summary", {})

    _log(
        "briefing_built",
        topic=topic,
        primary=len(primary_narratives),
        emerging=len(emerging_narratives),
        threads=len(threads),
        noise_suppressed=intel.get("noise_suppressed_count", 0),
        build_ms=elapsed_ms,
    )

    return {
        "topic": intel.get("topic", topic),
        "report_date": intel.get("report_date"),
        "available": True,
        "briefing": primary_narratives,
        "emerging_signals": emerging_narratives,
        "threads": threads,
        "meta": {
            "total_events_analyzed": signal_summary.get("event_count", len(all_events)),
            "primary_count": len(primary_narratives),
            "emerging_count": len(emerging_narratives),
            "noise_suppressed": intel.get("noise_suppressed_count", 0),
            "avg_signal_score": signal_summary.get("avg_signal_score"),
            "dedup_efficiency": signal_summary.get("dedup_efficiency"),
            "build_ms": elapsed_ms,
        },
    }
