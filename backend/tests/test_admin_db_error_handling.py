"""
Regression tests for Technical Debt #12 (resolved 2026-07-13): every
`try: conn = get_connection() except ValueError: raise HTTPException(503)`
block across app/admin/*_routes.py and app/public_routes.py now also
catches psycopg2.Error, not just ValueError.

Before this fix, a real DB outage (network down, bad credentials, Supabase
down) raised psycopg2.OperationalError from get_connection() itself — a
different exception type than the "DATABASE_URL not configured" ValueError
these blocks were written to catch — and propagated uncaught as a raw 500
instead of the same clean 503 the rest of each handler produces.

One representative route per file is covered here (feed-lifecycle and
feed-recommendation routes already have their own regression tests in
tests/test_admin_feed_lifecycle.py). All DB access is mocked — no test
hits the real Supabase instance.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import psycopg2

import app.main as main


class AdminDbErrorHandlingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("ADMIN_API_KEY", None)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()


class FeedLifecycleConnectionFailureTests(AdminDbErrorHandlingTestCase):
    def test_disable_feed_returns_503_on_connection_failure(self) -> None:
        with patch(
            "app.admin.feed_lifecycle_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.post("/admin/feeds/1/disable")
        self.assertEqual(response.status_code, 503)


class PipelineRoutesConnectionFailureTests(AdminDbErrorHandlingTestCase):
    def test_generate_report_returns_503_on_connection_failure(self) -> None:
        with patch(
            "app.admin.pipeline_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.post(
                "/admin/generate-report", params={"topic": "Technology"}
            )
        self.assertEqual(response.status_code, 503)


class ExportRoutesConnectionFailureTests(AdminDbErrorHandlingTestCase):
    def test_export_briefing_returns_503_on_connection_failure(self) -> None:
        with patch(
            "app.admin.export_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.get("/admin/export/briefing", params={"topic": "Technology"})
        self.assertEqual(response.status_code, 503)


class DiagnosticsRoutesConnectionFailureTests(AdminDbErrorHandlingTestCase):
    def test_generation_runs_returns_503_on_connection_failure(self) -> None:
        # Not /admin/system-status: that route deliberately swallows any
        # get_connection()/query exception (`except Exception: pass`) and
        # always returns 200 with nulled-out last-run fields — Technical
        # Debt #10, "generation_runs tracking is optional," a separate,
        # already-known, unrelated design choice. /admin/generation-runs
        # is the route in this file with the actual #12 pattern.
        with patch(
            "app.admin.diagnostics_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.get("/admin/generation-runs")
        self.assertEqual(response.status_code, 503)


class PublicRoutesConnectionFailureTests(unittest.TestCase):
    """No ADMIN_API_KEY gate on these — public endpoints."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        self.client = TestClient(main.app)

    def test_register_device_returns_503_on_connection_failure(self) -> None:
        with patch(
            "app.public_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.post("/devices", json={"push_token": "tok-123"})
        self.assertEqual(response.status_code, 503)

    def test_daily_report_falls_back_to_mock_on_connection_failure(self) -> None:
        # Unlike the admin routes above, /daily-report deliberately degrades
        # to MOCK_REPORT on any get_connection() failure (not just a missing
        # DATABASE_URL) rather than raising — see Technical Debt #7's
        # resolution. A real outage should serve stale/mock content here,
        # not a hard error, same as the "not configured" case already did.
        with patch(
            "app.public_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.get("/daily-report")
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())


if __name__ == "__main__":
    unittest.main()
