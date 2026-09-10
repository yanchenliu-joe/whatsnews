"""Tests for the multi-slot daily pipeline (Phase 34, added 2026-07-06).

The scheduler can now wake for several configured times per day
(SCHEDULER_DAILY_TIME as a comma-separated list) instead of just one, so
content stays fresh for users whose notification time is later in the day.
Each daily-mode wake forces regenerate=True through to the
perspective/watch-next/narrative stages (which otherwise skip regeneration
if today's version is already "ready"). Assembly/editorial/WIM already
replace/re-evaluate on every call regardless and needed no changes.
No test hits the real Supabase instance, Expo push API, or OpenAI.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import app.main as main
from app.pipeline.orchestrator import run_scheduled_pipeline
from app.pipeline.scheduler import seconds_until_next_run


class SecondsUntilNextRunMultiSlotTests(unittest.TestCase):
    def test_single_time_behaves_like_before(self) -> None:
        with patch("app.pipeline.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 6, 6, 0, tzinfo=ZoneInfo("UTC"))
            delay, next_run = seconds_until_next_run(["07:00"], "UTC")
        self.assertAlmostEqual(delay, 3600, delta=1)
        self.assertEqual(next_run.hour, 7)

    def test_picks_soonest_of_several_times(self) -> None:
        with patch("app.pipeline.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 6, 8, 0, tzinfo=ZoneInfo("UTC"))
            delay, next_run = seconds_until_next_run(["07:00", "12:00", "18:00"], "UTC")
        self.assertEqual(next_run.hour, 12)
        self.assertAlmostEqual(delay, 4 * 3600, delta=1)

    def test_rolls_to_tomorrows_first_slot_when_all_today_passed(self) -> None:
        with patch("app.pipeline.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 6, 20, 0, tzinfo=ZoneInfo("UTC"))
            delay, next_run = seconds_until_next_run(["07:00", "12:00", "18:00"], "UTC")
        self.assertEqual(next_run.day, 7)
        self.assertEqual(next_run.hour, 7)
        self.assertAlmostEqual(delay, 11 * 3600, delta=1)

    def test_rejects_a_raw_comma_separated_string_not_a_list(self) -> None:
        # Found in production (2026-07-07): admin_system_status() passed the
        # raw os.getenv() string straight through instead of splitting it
        # first, so iterating "07:00,12:00,18:00" character-by-character blew
        # up with "not enough values to unpack" the moment ENABLE_SCHEDULER
        # was true with a multi-slot SCHEDULER_DAILY_TIME (i.e. never hit
        # locally with the single-slot dev default, only in production).
        with self.assertRaises(ValueError):
            seconds_until_next_run("07:00,12:00,18:00", "UTC")


class AdminSystemStatusMultiSlotTests(unittest.TestCase):
    """Regression test for the bug above, at the actual route level."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        self._env_patch = patch.dict(
            os.environ,
            {
                "ENABLE_SCHEDULER": "true",
                "SCHEDULER_DAILY_TIME": "07:00,12:00,18:00",
                "SCHEDULER_TIMEZONE": "America/Los_Angeles",
            },
            clear=False,
        )
        self._env_patch.start()
        os.environ.pop("ADMIN_API_KEY", None)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()

    @patch("app.admin.diagnostics_routes.get_connection", side_effect=RuntimeError("no db in this test"))
    def test_multi_slot_daily_time_does_not_500(self, _mock_conn) -> None:
        response = self.client.get("/admin/system-status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["scheduler_mode"], "daily")
        self.assertIsNotNone(body["next_scheduled_run"])


class RunScheduledPipelineRegenerateThreadingTests(unittest.TestCase):
    def _patched(self):
        return [
            patch("app.pipeline.orchestrator.get_connection", side_effect=ValueError("no db")),
            patch("app.pipeline.orchestrator.ingest_all_active_sources", return_value={
                "topics_processed": 0, "articles_inserted": 0,
                "articles_skipped": 0, "errors_count": 0,
            }),
            patch("app.pipeline.orchestrator.assemble_all_active_topics", return_value={
                "topics_processed": 0, "total_assigned": 0, "errors_count": 0,
            }),
            patch("app.ingestion.og_image.fill_missing_og_images", return_value={
                "articles_checked": 0, "fetched": 0, "updated": 0,
            }),
            patch("app.editorial.service.run_editorial_engine", return_value={
                "articles_processed": 0, "average_importance": 0, "metadata_persisted": 0,
            }),
            patch("app.perspective.service.generate_daily_perspective", return_value={
                "status": "ok", "perspective_status": "ready",
            }),
            patch("app.watch_next.service.generate_daily_watch_next", return_value={
                "status": "ok", "watch_next_status": "ready",
            }),
            patch("app.narrative.service.generate_daily_narrative", return_value={
                "status": "ok", "report_date": None,
            }),
        ]

    def test_regenerate_true_threads_to_all_three_regenerable_stages(self) -> None:
        patchers = self._patched()
        mocks = [p.start() for p in patchers]
        try:
            run_scheduled_pipeline(regenerate=True)
        finally:
            for p in patchers:
                p.stop()

        mock_perspective, mock_watch_next, mock_narrative = mocks[5], mocks[6], mocks[7]
        mock_perspective.assert_called_once_with(regenerate=True)
        mock_watch_next.assert_called_once_with(regenerate=True)
        mock_narrative.assert_called_once_with(regenerate=True)

    def test_default_regenerate_is_false(self) -> None:
        patchers = self._patched()
        mocks = [p.start() for p in patchers]
        try:
            run_scheduled_pipeline()
        finally:
            for p in patchers:
                p.stop()

        mock_perspective, mock_watch_next, mock_narrative = mocks[5], mocks[6], mocks[7]
        mock_perspective.assert_called_once_with(regenerate=False)
        mock_watch_next.assert_called_once_with(regenerate=False)
        mock_narrative.assert_called_once_with(regenerate=False)


if __name__ == "__main__":
    unittest.main()
