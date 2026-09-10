"""
Tests for the archive retention cleanup job (app/retention/). All DB calls
and audio file deletion are mocked — no real Postgres/Supabase Storage
calls are made.
"""

from __future__ import annotations

import os
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.retention.config import (
    get_cleanup_tick_seconds,
    get_product_events_retention_days,
    get_retention_days,
)
from app.retention.service import run_archive_cleanup


class ConfigTests(unittest.TestCase):
    def test_retention_days_defaults_to_seven(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ARCHIVE_RETENTION_DAYS", None)
            self.assertEqual(get_retention_days(), 7)

    def test_retention_days_reads_env_override(self) -> None:
        with patch.dict(os.environ, {"ARCHIVE_RETENTION_DAYS": "30"}):
            self.assertEqual(get_retention_days(), 30)

    def test_cleanup_tick_seconds_defaults_to_24h(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ARCHIVE_CLEANUP_TICK_SECONDS", None)
            self.assertEqual(get_cleanup_tick_seconds(), 86400)

    def test_product_events_retention_days_defaults_to_ninety(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRODUCT_EVENTS_RETENTION_DAYS", None)
            self.assertEqual(get_product_events_retention_days(), 90)

    def test_product_events_retention_days_reads_env_override(self) -> None:
        with patch.dict(os.environ, {"PRODUCT_EVENTS_RETENTION_DAYS": "180"}):
            self.assertEqual(get_product_events_retention_days(), 180)


def _mock_conn_with_narrative_rows(narrative_rows: list[dict]):
    """
    Builds a mock connection whose cursor returns narrative_rows for the
    first SELECT (audio file lookup) and a fixed rowcount for every
    subsequent DELETE. Mirrors the real cursor's fetchall()/rowcount shape.
    """
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = narrative_rows
    # rowcount is read after each DELETE — give each a distinct value so
    # tests can assert the right count landed in the right stats key.
    mock_cur.rowcount = 1
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


class RunArchiveCleanupTests(unittest.TestCase):
    def test_deletes_from_all_report_scoped_tables_with_the_same_cutoff(self) -> None:
        mock_conn, mock_cur = _mock_conn_with_narrative_rows([])
        with patch("app.retention.service.get_connection", return_value=mock_conn), \
             patch("app.retention.service.get_retention_days", return_value=7), \
             patch("app.retention.service.get_product_events_retention_days", return_value=90):
            stats = run_archive_cleanup()

        expected_cutoff = date.today() - timedelta(days=7)
        expected_events_cutoff = date.today() - timedelta(days=90)
        self.assertEqual(stats["cutoff_date"], expected_cutoff.isoformat())

        executed_sql = [c.args[0] for c in mock_cur.execute.call_args_list]
        self.assertTrue(any("FROM briefing_narratives" in s and "SELECT" in s for s in executed_sql))
        self.assertTrue(any(s.startswith("DELETE FROM daily_reports") for s in executed_sql))
        self.assertTrue(
            any(s.startswith("DELETE FROM articles") and "report_id IS NULL" in s for s in executed_sql)
        )
        self.assertTrue(any(s.startswith("DELETE FROM briefing_narratives") for s in executed_sql))
        self.assertTrue(any(s.startswith("DELETE FROM editorial_perspectives") for s in executed_sql))
        self.assertTrue(any(s.startswith("DELETE FROM editorial_watch_next") for s in executed_sql))
        self.assertTrue(any(s.startswith("DELETE FROM generation_runs") for s in executed_sql))
        self.assertTrue(any(s.startswith("DELETE FROM product_events") for s in executed_sql))

        # Every DELETE/the audio SELECT *except* product_events (which has
        # its own, separately-configured, longer window) should use the
        # identical report-scoped cutoff param.
        for c in mock_cur.execute.call_args_list:
            if len(c.args) > 1 and not c.args[0].startswith("DELETE FROM product_events"):
                self.assertIn(expected_cutoff, c.args[1])

        # product_events gets its own, independently-computed cutoff.
        product_events_call = next(
            c for c in mock_cur.execute.call_args_list
            if c.args[0].startswith("DELETE FROM product_events")
        )
        self.assertIn(expected_events_cutoff, product_events_call.args[1])

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_custom_retention_days_overrides_config_default(self) -> None:
        mock_conn, mock_cur = _mock_conn_with_narrative_rows([])
        with patch("app.retention.service.get_connection", return_value=mock_conn):
            stats = run_archive_cleanup(retention_days=30)
        self.assertEqual(stats["retention_days"], 30)
        self.assertEqual(stats["cutoff_date"], (date.today() - timedelta(days=30)).isoformat())

    def test_custom_product_events_retention_days_overrides_config_default(self) -> None:
        mock_conn, mock_cur = _mock_conn_with_narrative_rows([])
        with patch("app.retention.service.get_connection", return_value=mock_conn):
            stats = run_archive_cleanup(retention_days=7, product_events_retention_days=180)
        self.assertEqual(stats["product_events_retention_days"], 180)
        self.assertEqual(
            stats["product_events_cutoff_date"],
            (date.today() - timedelta(days=180)).isoformat(),
        )
        # Independent from the report-scoped retention_days — confirms the
        # two windows don't accidentally collapse into one.
        self.assertEqual(stats["retention_days"], 7)

    def test_product_events_deleted_count_reflected_in_stats(self) -> None:
        mock_conn, mock_cur = _mock_conn_with_narrative_rows([])
        mock_cur.rowcount = 42
        with patch("app.retention.service.get_connection", return_value=mock_conn):
            stats = run_archive_cleanup(retention_days=7)
        self.assertEqual(stats["product_events_deleted"], 42)

    def test_deletes_audio_files_before_deleting_the_narrative_rows(self) -> None:
        narrative_rows = [{"scope": "daily", "report_date": "2026-06-01", "version": 1}]
        mock_conn, mock_cur = _mock_conn_with_narrative_rows(narrative_rows)

        call_order: list[str] = []

        def _record(sql, *args):
            call_order.append("select_narratives" if "SELECT scope" in sql else sql)

        mock_cur.execute.side_effect = _record

        with patch("app.retention.service.get_connection", return_value=mock_conn), \
             patch("app.retention.service.delete_audio_file", return_value=True) as mock_delete_audio:
            stats = run_archive_cleanup(retention_days=7)

        # One delete_audio_file call per (narrative row x voice profile).
        self.assertEqual(mock_delete_audio.call_count, len({"female", "male"}))
        mock_delete_audio.assert_any_call("daily", "2026-06-01", 1, "female")
        mock_delete_audio.assert_any_call("daily", "2026-06-01", 1, "male")
        self.assertEqual(stats["audio_files_deleted"], 2)
        self.assertEqual(stats["audio_files_failed"], 0)

        # The narrative SELECT must be the very first statement executed —
        # deleting the row first would lose the scope/version needed to
        # reconstruct the filename.
        self.assertEqual(call_order[0], "select_narratives")

    def test_audio_deletion_failure_is_counted_not_raised(self) -> None:
        narrative_rows = [{"scope": "daily", "report_date": "2026-06-01", "version": 1}]
        mock_conn, mock_cur = _mock_conn_with_narrative_rows(narrative_rows)

        with patch("app.retention.service.get_connection", return_value=mock_conn), \
             patch("app.retention.service.delete_audio_file", return_value=False):
            stats = run_archive_cleanup(retention_days=7)

        self.assertEqual(stats["audio_files_deleted"], 0)
        self.assertEqual(stats["audio_files_failed"], 2)
        # A failed file delete must not abort the DB cleanup.
        mock_conn.commit.assert_called_once()

    def test_db_error_rolls_back_and_reraises(self) -> None:
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_cur.execute.side_effect = [None, RuntimeError("db exploded")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        with patch("app.retention.service.get_connection", return_value=mock_conn):
            with self.assertRaises(RuntimeError):
                run_archive_cleanup(retention_days=7)

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    def test_stats_shape_matches_all_deleted_tables(self) -> None:
        mock_conn, mock_cur = _mock_conn_with_narrative_rows([])
        with patch("app.retention.service.get_connection", return_value=mock_conn):
            stats = run_archive_cleanup(retention_days=7)

        for key in (
            "retention_days",
            "cutoff_date",
            "daily_reports_deleted",
            "orphan_articles_deleted",
            "narratives_deleted",
            "perspectives_deleted",
            "watch_next_deleted",
            "generation_runs_deleted",
            "audio_files_deleted",
            "audio_files_failed",
            "product_events_retention_days",
            "product_events_cutoff_date",
            "product_events_deleted",
        ):
            self.assertIn(key, stats)


if __name__ == "__main__":
    unittest.main()
