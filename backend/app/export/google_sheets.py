"""Export ExportBundle rows to Google Sheets via service account."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import gspread
from gspread.exceptions import APIError, GSpreadException, SpreadsheetNotFound
from google.oauth2.service_account import Credentials

from app.export.models import ExportBundle

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_TAB_NAME = "Daily Briefings"

HEADER_ROW = [
    "exported_at",
    "report_date",
    "topic",
    "article_index",
    "title",
    "source",
    "published_at",
    "summary",
    "why_it_matters",
    "url",
]

_SENSITIVE_PATTERNS = (
    re.compile(r'"private_key"\s*:\s*"[^"]*"', re.IGNORECASE),
    re.compile(r"-----BEGIN[A-Z ]+-----[\s\S]*?-----END[A-Z ]+-----"),
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r'"client_email"\s*:\s*"[^"]+@[^"]+"', re.IGNORECASE),
)


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


class GoogleSheetsConfigError(Exception):
    """Missing or invalid Google Sheets configuration."""


class GoogleSheetsExportError(Exception):
    """Google Sheets API operation failed."""


def _sanitize_message(text: str) -> str:
    """Remove credential material from an error string."""
    cleaned = text
    for pattern in _SENSITIVE_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    return cleaned.strip()


def _exception_message(exc: Exception) -> str:
    """Best-effort message when str(exc) may be empty."""
    text = str(exc).strip()
    if not text:
        text = repr(exc).strip()
    return _sanitize_message(text)


def _format_export_error(exc: Exception) -> str:
    """Return a safe, user-facing message without credential contents."""
    cls = type(exc).__name__

    if isinstance(exc, SpreadsheetNotFound):
        return (
            f"{cls}: Spreadsheet not found or not accessible. "
            "Check GOOGLE_SHEET_ID and share the sheet with the service account."
        )
    if isinstance(exc, APIError):
        api_message = _sanitize_message(
            str(exc.error.get("message", "")) if getattr(exc, "error", None) else ""
        )
        if not api_message:
            api_message = _exception_message(exc)
        if exc.code == 403:
            return (
                f"{cls}: Permission denied. Share the Google Sheet with the service "
                "account email (Editor) from your credentials JSON client_email field."
            )
        if exc.code == 404:
            return (
                f"{cls}: Spreadsheet or worksheet not found. "
                "Check GOOGLE_SHEET_ID and tab name."
            )
        return f"{cls} ({exc.code}): {api_message or 'unknown API error'}"

    msg = _exception_message(exc)
    lower = msg.lower()
    if "permission" in lower or "denied" in lower or "403" in lower:
        return (
            f"{cls}: Permission denied. Share the Google Sheet with the service "
            "account email (Editor) from your credentials JSON client_email field."
        )
    if "not found" in lower:
        return (
            f"{cls}: Spreadsheet not found or not accessible. "
            "Check GOOGLE_SHEET_ID and share the sheet with the service account."
        )
    if msg:
        return f"{cls}: {msg[:200]}"
    return f"{cls}: Google Sheets export failed with no error message"


def _log_export_failure(exc: Exception) -> None:
    detail = _format_export_error(exc)
    _log(
        "google_sheet_export_failed",
        exception=repr(exc),
        error=detail,
    )


def _load_service_account_info() -> dict[str, Any]:
    inline = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if inline is not None:
        inline = inline.strip()
    if inline:
        try:
            return json.loads(inline)
        except json.JSONDecodeError as e:
            raise GoogleSheetsConfigError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from e

    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if path:
        path = path.strip()
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except OSError as e:
            raise GoogleSheetsConfigError(
                f"Could not read GOOGLE_APPLICATION_CREDENTIALS file: {path}"
            ) from e
        except json.JSONDecodeError as e:
            raise GoogleSheetsConfigError(
                "GOOGLE_APPLICATION_CREDENTIALS file is not valid JSON."
            ) from e

    raise GoogleSheetsConfigError(
        "Google credentials not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON "
        "or GOOGLE_APPLICATION_CREDENTIALS."
    )


def get_gspread_client() -> gspread.Client:
    info = _load_service_account_info()
    try:
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    except (ValueError, KeyError) as e:
        raise GoogleSheetsConfigError(
            f"Service account credentials are invalid or incomplete: {e}"
        ) from e
    return gspread.authorize(creds)


def bundle_to_rows(bundle: ExportBundle) -> list[list[str]]:
    """Flatten an ExportBundle into sheet rows (no header)."""
    rows: list[list[str]] = []
    exported_at = bundle.generated_at
    for topic in bundle.topics:
        for article in topic.articles:
            url = article.url or article.raw_url or ""
            rows.append([
                exported_at,
                topic.report_date,
                topic.topic,
                str(article.position),
                article.title,
                article.source,
                article.published_at or "",
                article.summary,
                article.why_it_matters,
                url,
            ])
    return rows


def export_bundle_to_sheet(
    bundle: ExportBundle,
    *,
    sheet_id: str | None = None,
    tab_name: str | None = None,
) -> dict[str, Any]:
    """
    Append briefing rows to a Google Sheet tab (v1: append-only, no dedup).

    Creates the worksheet if it does not exist. Writes a header row when the
    sheet is empty.
    """
    resolved_sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID")
    if not resolved_sheet_id:
        raise GoogleSheetsConfigError(
            "GOOGLE_SHEET_ID is not set and no sheet_id was provided."
        )

    resolved_tab = tab_name or os.getenv("GOOGLE_SHEET_TAB_NAME") or DEFAULT_TAB_NAME
    rows = bundle_to_rows(bundle)
    if not rows:
        _log(
            "google_sheet_export_skipped",
            reason="no_articles",
            sheet_id=resolved_sheet_id,
            tab_name=resolved_tab,
        )
        return {
            "ok": True,
            "sheet_id": resolved_sheet_id,
            "tab_name": resolved_tab,
            "rows_appended": 0,
            "report_date": bundle.export_date,
        }

    _log(
        "google_sheet_export_starting",
        sheet_id=resolved_sheet_id,
        tab_name=resolved_tab,
        report_date=bundle.export_date,
        article_count=len(rows),
    )

    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(resolved_sheet_id)
        try:
            worksheet = spreadsheet.worksheet(resolved_tab)
        except gspread.WorksheetNotFound:
            _log("google_sheet_tab_creating", tab_name=resolved_tab, sheet_id=resolved_sheet_id)
            worksheet = spreadsheet.add_worksheet(
                title=resolved_tab,
                rows=max(len(rows) + 1, 100),
                cols=len(HEADER_ROW),
            )

        existing = worksheet.get_all_values()
        if not existing:
            worksheet.append_row(HEADER_ROW, value_input_option="RAW")
            _log("google_sheet_header_written", tab_name=resolved_tab)

        worksheet.append_rows(rows, value_input_option="RAW")
    except GoogleSheetsConfigError as e:
        _log("google_sheet_export_config_error", sheet_id=resolved_sheet_id, exception=repr(e))
        raise
    except (GSpreadException, OSError) as e:
        detail = _format_export_error(e)
        _log_export_failure(e)
        raise GoogleSheetsExportError(detail) from e
    except Exception as e:
        detail = _format_export_error(e)
        _log_export_failure(e)
        raise GoogleSheetsExportError(detail) from e

    _log(
        "google_sheet_export_done",
        sheet_id=resolved_sheet_id,
        tab_name=resolved_tab,
        rows_appended=len(rows),
        report_date=bundle.export_date,
    )

    return {
        "ok": True,
        "sheet_id": resolved_sheet_id,
        "tab_name": resolved_tab,
        "rows_appended": len(rows),
        "report_date": bundle.export_date,
    }
