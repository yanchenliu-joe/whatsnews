"""Persist and load daily Watch Next."""

from __future__ import annotations

import json
from datetime import date
from typing import Any


def _row_to_api_dict(row: dict) -> dict[str, Any]:
    payload = row.get("watch_json") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    out = dict(payload) if isinstance(payload, dict) else {}
    out["id"] = row["id"]
    out["status"] = row["status"]
    out["version"] = row["version"]
    out["report_date"] = str(row["report_date"])
    out["items"] = out.get("items") or []
    out["generation_method"] = row.get("generation_method")
    out["error_message"] = row.get("error_message")
    out["generated_at"] = out.get("generated_at")
    out["quality_gate"] = out.get("quality_gate") or {}
    out["item_count"] = row.get("item_count") or len(out["items"])
    return out


def get_ready_watch_next(cur, report_date: date) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM editorial_watch_next
        WHERE report_date = %s AND status = 'ready'
        ORDER BY version DESC
        LIMIT 1
        """,
        (report_date,),
    )
    row = cur.fetchone()
    return _row_to_api_dict(dict(row)) if row else None


def get_next_version(cur, report_date: date) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(version), 0) AS max_v
        FROM editorial_watch_next
        WHERE report_date = %s
        """,
        (report_date,),
    )
    return int(cur.fetchone()["max_v"]) + 1


def insert_watch_next(cur, watch_next) -> int:
    payload = watch_next.to_dict()
    payload["quality_gate"] = watch_next.quality_gate
    cur.execute(
        """
        INSERT INTO editorial_watch_next (
            report_date,
            status,
            watch_json,
            item_count,
            generation_method,
            error_message,
            version,
            updated_at
        )
        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, NOW())
        RETURNING id
        """,
        (
            watch_next.report_date,
            watch_next.status,
            json.dumps(payload),
            len(watch_next.items),
            watch_next.generation_method,
            watch_next.error_message,
            watch_next.version,
        ),
    )
    return int(cur.fetchone()["id"])
