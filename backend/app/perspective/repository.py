"""Persist and load editorial perspectives."""

from __future__ import annotations

import json
from datetime import date
from typing import Any


def _row_to_api_dict(row: dict) -> dict[str, Any]:
    payload = row.get("perspective_json") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    out = dict(payload) if isinstance(payload, dict) else {}
    out["id"] = row["id"]
    out["status"] = row["status"]
    out["version"] = row["version"]
    out["report_date"] = str(row["report_date"])
    out["headline"] = row.get("headline") or out.get("headline") or ""
    out["perspective"] = row.get("perspective_text") or out.get("perspective") or ""
    out["confidence"] = row.get("confidence") or out.get("confidence")
    out["themes"] = row.get("themes") or out.get("themes") or []
    out["supporting_evidence"] = out.get("supporting_evidence") or []
    out["watch_next"] = out.get("watch_next") or []
    out["generation_method"] = row.get("generation_method")
    out["error_message"] = row.get("error_message")
    out["generated_at"] = out.get("generated_at")
    out["quality_gate"] = out.get("quality_gate") or {}
    return out


def get_ready_perspective(cur, report_date: date) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM editorial_perspectives
        WHERE report_date = %s AND status = 'ready'
        ORDER BY version DESC
        LIMIT 1
        """,
        (report_date,),
    )
    row = cur.fetchone()
    return _row_to_api_dict(dict(row)) if row else None


def get_latest_ready_perspective(cur) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT *
        FROM editorial_perspectives
        WHERE status = 'ready'
        ORDER BY report_date DESC, version DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return _row_to_api_dict(dict(row)) if row else None


def get_next_version(cur, report_date: date) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(version), 0) AS max_v
        FROM editorial_perspectives
        WHERE report_date = %s
        """,
        (report_date,),
    )
    return int(cur.fetchone()["max_v"]) + 1


def insert_perspective(cur, perspective) -> int:
    payload = perspective.to_dict()
    payload["quality_gate"] = perspective.quality_gate
    cur.execute(
        """
        INSERT INTO editorial_perspectives (
            report_date,
            status,
            perspective_json,
            headline,
            perspective_text,
            confidence,
            themes,
            supporting_article_ids,
            generation_method,
            error_message,
            version,
            updated_at
        )
        VALUES (
            %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, NOW()
        )
        RETURNING id
        """,
        (
            perspective.report_date,
            perspective.status,
            json.dumps(payload),
            perspective.headline,
            perspective.perspective,
            perspective.confidence,
            json.dumps(perspective.themes),
            json.dumps(perspective.supporting_article_ids),
            perspective.generation_method,
            perspective.error_message,
            perspective.version,
        ),
    )
    return int(cur.fetchone()["id"])
