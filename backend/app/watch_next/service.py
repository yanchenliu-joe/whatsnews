"""Orchestrate daily Watch Next generation."""

from __future__ import annotations

import time
from datetime import date

from app.briefing_repository import get_latest_daily_report_date
from app.database import get_connection
from app.perspective.loader import load_perspective_articles
from app.perspective.repository import get_ready_perspective
from app.watch_next.generator import build_daily_watch_next, watch_next_generated_at
from app.watch_next.metrics import normalize_watch_next_stats
from app.watch_next.models import DailyWatchNext, WatchNextItem
from app.watch_next.quality import run_watch_next_quality_gate
from app.watch_next.repository import get_next_version, get_ready_watch_next, insert_watch_next


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _confidence_distribution(items: list[WatchNextItem]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for item in items:
        key = item.confidence or "medium"
        dist[key] = dist.get(key, 0) + 1
    return dist


def _stats_from_result(result: dict, elapsed: float) -> dict:
    return normalize_watch_next_stats(
        {
            "status": result.get("status", "completed"),
            "watch_next_status": result.get("watch_next_status"),
            "watch_next_item_count": result.get("watch_next_item_count", 0),
            "watch_next_confidence_distribution": result.get(
                "watch_next_confidence_distribution", {}
            ),
            "watch_next_generation_seconds": elapsed,
            "watch_next_id": result.get("watch_next_id"),
            "version": result.get("version"),
            "quality_gate": result.get("quality_gate"),
            "reason": result.get("reason"),
            "error": result.get("error"),
        }
    )


def generate_daily_watch_next(
    report_date: date | None = None,
    *,
    regenerate: bool = False,
) -> dict:
    """Generate and persist daily Watch Next. Does not raise."""
    started = time.perf_counter()
    try:
        conn = get_connection()
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return _stats_from_result(
            {
                "status": "error",
                "watch_next_status": "failed",
                "error": str(exc)[:500],
            },
            elapsed,
        )

    cur = conn.cursor()
    try:
        target_date = report_date or get_latest_daily_report_date(cur) or date.today()
        date_str = str(target_date)

        if not regenerate:
            existing = get_ready_watch_next(cur, target_date)
            if existing:
                _log("watch_next_skipped", report_date=date_str, reason="ready_exists")
                elapsed = time.perf_counter() - started
                return _stats_from_result(
                    {
                        "status": "skipped",
                        "reason": "ready_exists",
                        "watch_next_status": "ready",
                        "watch_next_item_count": existing.get("item_count", 0),
                        "watch_next_confidence_distribution": _confidence_distribution(
                            [
                                WatchNextItem(**item)
                                for item in (existing.get("items") or [])
                                if isinstance(item, dict)
                            ]
                        ),
                        "watch_next_id": existing.get("id"),
                        "version": existing.get("version"),
                    },
                    elapsed,
                )

        articles, _topic_count = load_perspective_articles(cur, target_date)
        if not articles:
            elapsed = time.perf_counter() - started
            return _stats_from_result(
                {
                    "status": "skipped",
                    "reason": "no_publishable_articles",
                    "watch_next_status": "missing",
                },
                elapsed,
            )

        perspective = get_ready_perspective(cur, target_date)
        raw_items, _debug = build_daily_watch_next(
            target_date, articles, perspective=perspective
        )
        items = [
            WatchNextItem(
                text=item["text"],
                reason=item["reason"],
                topics=item.get("topics") or [],
                impact_types=item.get("impact_types") or [],
                supporting_article_ids=item.get("supporting_article_ids") or [],
                confidence=item.get("confidence") or "medium",
            )
            for item in raw_items
        ]

        quality = run_watch_next_quality_gate([i.to_dict() for i in items])
        watch_next = DailyWatchNext(
            report_date=target_date,
            items=items,
            generated_at=watch_next_generated_at(),
            generation_method="rule_v1",
            quality_gate=quality,
        )

        if quality["passed"]:
            watch_next.status = "ready"
            watch_next.error_message = None
        else:
            watch_next.status = "failed"
            watch_next.error_message = "; ".join(quality.get("errors") or [])

        watch_next.version = get_next_version(cur, target_date)
        watch_next_id = insert_watch_next(cur, watch_next)
        conn.commit()

        elapsed = time.perf_counter() - started
        result = {
            "status": "success" if watch_next.status == "ready" else "failed",
            "report_date": date_str,
            "watch_next_id": watch_next_id,
            "version": watch_next.version,
            "watch_next_status": watch_next.status,
            "watch_next_item_count": len(items),
            "watch_next_confidence_distribution": _confidence_distribution(items),
            "quality_gate": quality,
            "items": [i.to_dict() for i in items],
        }

        if watch_next.status == "ready":
            _log(
                "watch_next_success",
                report_date=date_str,
                items=len(items),
                version=watch_next.version,
            )
        else:
            _log(
                "watch_next_failed",
                report_date=date_str,
                error=watch_next.error_message,
            )

        return _stats_from_result(result, elapsed)

    except Exception as exc:
        conn.rollback()
        elapsed = time.perf_counter() - started
        _log("watch_next_error", error=str(exc)[:300])
        return _stats_from_result(
            {
                "status": "error",
                "watch_next_status": "failed",
                "error": str(exc)[:500],
            },
            elapsed,
        )
    finally:
        cur.close()
        conn.close()


def load_watch_next_for_api(report_date: date | None = None) -> dict | None:
    try:
        conn = get_connection()
    except ValueError:
        return None

    cur = conn.cursor()
    try:
        if report_date is None:
            anchor = get_latest_daily_report_date(cur)
            if not anchor:
                return None
            report_date = anchor

        ready = get_ready_watch_next(cur, report_date)
        if ready:
            return ready

        return {
            "report_date": str(report_date),
            "status": "missing",
            "items": [],
        }
    finally:
        cur.close()
        conn.close()
