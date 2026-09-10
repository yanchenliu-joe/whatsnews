"""Admin export routes — briefing export (JSON/PDF) + Google Sheets append."""

from __future__ import annotations

from datetime import date
from typing import Optional

import psycopg2
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.database import get_connection
from app.export import (
    ExportQualityError,
    GoogleSheetsConfigError,
    GoogleSheetsExportError,
    export_bundle_to_sheet,
    load_exportable_briefing,
    render_pdf,
)
from app.log_utils import _log


class GoogleSheetExportRequest(BaseModel):
    date: Optional[str] = None
    topic: Optional[str] = None
    sheet_id: Optional[str] = None
    tab_name: Optional[str] = None


def register_admin_export_routes(app: FastAPI, require_admin_key) -> None:
    """Attach /admin/export/* endpoints. require_admin_key is app.admin.deps.require_admin_key."""

    @app.get("/admin/export/briefing")
    def admin_export_briefing(
        format: str = "json",
        export_date_str: Optional[str] = Query(default=None, alias="date"),
        topic: Optional[str] = None,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Export assembled daily briefing(s) as JSON or PDF.

        Only articles linked to daily_reports via report_id are included.
        Returns 409 if any included article is missing why_it_matters.
        Under-filled topics produce warnings in quality_gate but do not block export.

        - format=json|pdf (default json)
        - date=YYYY-MM-DD (optional; default latest report per topic)
        - topic=<name> (optional; default all active topics)

        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)

        fmt = format.lower().strip()
        if fmt not in ("json", "pdf"):
            raise HTTPException(
                status_code=400,
                detail="Invalid format. Use format=json or format=pdf.",
            )

        export_date: date | None = None
        if export_date_str is not None:
            try:
                export_date = date.fromisoformat(export_date_str)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date. Use YYYY-MM-DD.",
                )

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            try:
                bundle = load_exportable_briefing(
                    cur,
                    export_date=export_date,
                    topic_name=topic,
                )
            finally:
                cur.close()
            conn.close()
        except ExportQualityError as e:
            raise HTTPException(
                status_code=409,
                detail={"error": e.message, **e.details},
            )
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        if fmt == "json":
            return bundle.to_dict()

        pdf_bytes = render_pdf(bundle)
        filename = f"whatsnews-briefing-{bundle.export_date}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/admin/export/google-sheet")
    def admin_export_google_sheet(
        body: GoogleSheetExportRequest | None = None,
        x_admin_key: Optional[str] = Header(default=None),
    ):
        """
        Append assembled briefing rows to a Google Sheet (v1: append-only).

        Reuses the same quality gate as GET /admin/export/briefing.
        Returns 409 if any included article is missing why_it_matters.

        Protected by ADMIN_API_KEY when that environment variable is set.
        """
        require_admin_key(x_admin_key)

        req = body or GoogleSheetExportRequest()
        export_date: date | None = None
        if req.date is not None:
            try:
                export_date = date.fromisoformat(req.date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date. Use YYYY-MM-DD.",
                )

        try:
            conn = get_connection()
        except (ValueError, psycopg2.Error) as e:
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")

        try:
            cur = conn.cursor()
            try:
                bundle = load_exportable_briefing(
                    cur,
                    export_date=export_date,
                    topic_name=req.topic,
                )
            finally:
                cur.close()
            conn.close()
        except ExportQualityError as e:
            raise HTTPException(
                status_code=409,
                detail={"error": e.message, **e.details},
            )
        except HTTPException:
            raise
        except Exception as e:
            _log("database_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Database error. Please try again.")

        try:
            result = export_bundle_to_sheet(
                bundle,
                sheet_id=req.sheet_id,
                tab_name=req.tab_name,
            )
            return result
        except GoogleSheetsConfigError as e:
            _log("admin_google_sheet_export_config_error", error=str(e)[:200])
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")
        except GoogleSheetsExportError as e:
            cause = e.__cause__
            _log(
                "admin_google_sheet_export_failed",
                exception=repr(cause) if cause else repr(e),
                error=str(e)[:200],
            )
            _log("internal_error_failed", error=str(e))
            raise HTTPException(status_code=503, detail="Internal server error. Please try again.")
