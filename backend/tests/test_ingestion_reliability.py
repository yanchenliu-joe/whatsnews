"""Tests for the ingestion-side feed reliability write path (Phase 24/24.2).

Covers `_update_feed_reliability` and `_update_feed_reliability_batch` (the
UPDATEs that increment failure_count/success_count/consecutive_failures on
news_sources after a real fetch), `_fetch_source_job`'s retry loop,
`fetch_sources_concurrently`'s aggregation, and `_load_active_topic_groups`'s
degraded/paused feed suppression logic.

As of the 2026-07-09 speed pass, `_fetch_source_job` no longer writes
reliability counters itself (was one DB connection per source, ~300/run) —
`fetch_sources_concurrently`/`fetch_all_sources_globally` now collect every
source's outcome and call `_update_feed_reliability_batch()` once per fetch
pass (`WHERE id = ANY(%s)` instead of `WHERE id = %s` x N). The single-row
`_update_feed_reliability` function still exists and is still exercised
directly by its own tests below; nothing calls it in the hot path anymore,
but it's kept for any caller that still wants a one-off update.

The CASE-based lifecycle transitions inside the UPDATE's SQL text (active→
degraded, degraded→active, auto-disable/auto-recover) are evaluated by
Postgres, not Python, so they can't be verified without a real database —
these tests instead lock in which branch (success vs failure) is executed,
with what parameters, and that commit/close/exception-swallowing behave as
documented. All DB access is mocked; no test touches the real Supabase
instance.
"""

from __future__ import annotations

import re
import unittest
from unittest.mock import MagicMock, call, patch

from app.ingestion.rss import FeedFetchResult
from app.ingestion.service import (
    _fetch_source_job,
    _load_active_topic_groups,
    _split_success_failure_ids,
    _update_feed_reliability,
    _update_feed_reliability_batch,
    fetch_sources_concurrently,
)


def _fake_conn() -> tuple[MagicMock, MagicMock]:
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


class UpdateFeedReliabilityTests(unittest.TestCase):
    def test_success_runs_the_success_count_branch(self) -> None:
        conn, cur = _fake_conn()
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _update_feed_reliability(42, success=True)

        query, params = cur.execute.call_args[0]
        query = _norm(query)
        self.assertIn("success_count = success_count + 1", query)
        self.assertIn("consecutive_failures = 0", query)
        self.assertEqual(params, (42,))
        conn.commit.assert_called_once()
        cur.close.assert_called_once()
        conn.close.assert_called_once()

    def test_failure_runs_the_failure_count_branch(self) -> None:
        conn, cur = _fake_conn()
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _update_feed_reliability(42, success=False)

        query, params = cur.execute.call_args[0]
        query = _norm(query)
        self.assertIn("failure_count = failure_count + 1", query)
        self.assertIn("consecutive_successes = 0", query)
        self.assertEqual(params, (42,))
        conn.commit.assert_called_once()

    def test_connection_error_is_silently_swallowed(self) -> None:
        with patch("app.ingestion.service.get_connection", side_effect=RuntimeError("db down")):
            _update_feed_reliability(42, success=True)  # must not raise

    def test_execute_error_is_silently_swallowed_but_cursor_still_closed(self) -> None:
        conn, cur = _fake_conn()
        cur.execute.side_effect = RuntimeError("query failed")
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _update_feed_reliability(42, success=True)  # must not raise
        cur.close.assert_called_once()
        conn.close.assert_called_once()
        conn.commit.assert_not_called()


class UpdateFeedReliabilityBatchTests(unittest.TestCase):
    def test_no_ids_skips_db_entirely(self) -> None:
        with patch("app.ingestion.service.get_connection") as mock_get_conn:
            _update_feed_reliability_batch([], [])
        mock_get_conn.assert_not_called()

    def test_success_ids_run_the_success_branch_with_any_array(self) -> None:
        conn, cur = _fake_conn()
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _update_feed_reliability_batch([1, 2, 3], [])

        cur.execute.assert_called_once()
        query, params = cur.execute.call_args[0]
        query = _norm(query)
        self.assertIn("success_count = success_count + 1", query)
        self.assertIn("WHERE id = ANY(%s)", query)
        self.assertEqual(params, ([1, 2, 3],))
        conn.commit.assert_called_once()
        cur.close.assert_called_once()
        conn.close.assert_called_once()

    def test_failure_ids_run_the_failure_branch_with_any_array(self) -> None:
        conn, cur = _fake_conn()
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _update_feed_reliability_batch([], [4, 5])

        cur.execute.assert_called_once()
        query, params = cur.execute.call_args[0]
        query = _norm(query)
        self.assertIn("failure_count = failure_count + 1", query)
        self.assertIn("WHERE id = ANY(%s)", query)
        self.assertEqual(params, ([4, 5],))
        conn.commit.assert_called_once()

    def test_mixed_success_and_failure_runs_both_branches_on_one_connection(self) -> None:
        conn, cur = _fake_conn()
        with patch("app.ingestion.service.get_connection", return_value=conn) as mock_get_conn:
            _update_feed_reliability_batch([1], [2])

        mock_get_conn.assert_called_once()
        self.assertEqual(cur.execute.call_count, 2)
        conn.commit.assert_called_once()

    def test_connection_error_is_silently_swallowed(self) -> None:
        with patch("app.ingestion.service.get_connection", side_effect=RuntimeError("db down")):
            _update_feed_reliability_batch([1], [])  # must not raise

    def test_execute_error_is_silently_swallowed_but_cursor_still_closed(self) -> None:
        conn, cur = _fake_conn()
        cur.execute.side_effect = RuntimeError("query failed")
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _update_feed_reliability_batch([1], [])  # must not raise
        cur.close.assert_called_once()
        conn.close.assert_called_once()
        conn.commit.assert_not_called()


class SplitSuccessFailureIdsTests(unittest.TestCase):
    def test_splits_by_status(self) -> None:
        results = [
            {"source_id": 1, "status": "ok"},
            {"source_id": 2, "status": "error"},
            {"source_id": 3, "status": "ok"},
        ]
        success_ids, failure_ids = _split_success_failure_ids(results)
        self.assertEqual(success_ids, [1, 3])
        self.assertEqual(failure_ids, [2])


class FetchSourceJobTests(unittest.TestCase):
    SRC = {"id": 7, "name": "Reuters", "feed_url": "https://example.com/rss"}

    def test_success_on_first_attempt_does_not_retry(self) -> None:
        ok_result = FeedFetchResult(articles=[{"title": "a"}], status="ok", error=None)
        with patch("app.ingestion.service.fetch_rss_feed_result", return_value=ok_result) as mock_fetch, \
             patch("app.ingestion.service.time.sleep") as mock_sleep:
            result = _fetch_source_job(self.SRC, topic_id=1, topic_name="Technology",
                                        max_items_per_feed=20, timeout_seconds=10)

        mock_fetch.assert_called_once()
        mock_sleep.assert_not_called()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["source_id"], 7)

    def test_all_attempts_failing_retries_twice_then_reports_failure(self) -> None:
        error_result = FeedFetchResult(articles=[], status="error", error="timeout")
        with patch("app.ingestion.service.fetch_rss_feed_result", return_value=error_result) as mock_fetch, \
             patch("app.ingestion.service.time.sleep") as mock_sleep:
            result = _fetch_source_job(self.SRC, topic_id=1, topic_name="Technology",
                                        max_items_per_feed=20, timeout_seconds=10)

        self.assertEqual(mock_fetch.call_count, 3)  # 1 initial + 2 retries
        mock_sleep.assert_has_calls([call(1.0), call(2.0)])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempts"], 3)

    def test_recovers_on_second_attempt(self) -> None:
        error_result = FeedFetchResult(articles=[], status="error", error="timeout")
        ok_result = FeedFetchResult(articles=[{"title": "a"}], status="ok", error=None)
        with patch("app.ingestion.service.fetch_rss_feed_result", side_effect=[error_result, ok_result]) as mock_fetch, \
             patch("app.ingestion.service.time.sleep") as mock_sleep:
            result = _fetch_source_job(self.SRC, topic_id=1, topic_name="Technology",
                                        max_items_per_feed=20, timeout_seconds=10)

        self.assertEqual(mock_fetch.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 2)


class FetchSourcesConcurrentlyTests(unittest.TestCase):
    def test_empty_sources_returns_empty_list(self) -> None:
        self.assertEqual(fetch_sources_concurrently([], "Technology"), [])

    def test_results_sorted_by_source_id_regardless_of_completion_order(self) -> None:
        sources = [{"id": 3, "name": "C", "feed_url": "u3"}, {"id": 1, "name": "A", "feed_url": "u1"}]

        def fake_job(src, topic_id, topic_name, max_items_per_feed, timeout_seconds):
            return {"source_id": src["id"], "source_name": src["name"], "status": "ok"}

        with patch("app.ingestion.service._fetch_source_job", side_effect=fake_job), \
             patch("app.ingestion.service._update_feed_reliability_batch") as mock_batch:
            results = fetch_sources_concurrently(sources, "Technology", topic_id=5)

        self.assertEqual([r["source_id"] for r in results], [1, 3])
        mock_batch.assert_called_once_with([1, 3], [])

    def test_worker_exception_produces_error_entry_without_crashing_batch(self) -> None:
        sources = [{"id": 1, "name": "Broken", "feed_url": "u1"}]
        with patch("app.ingestion.service._fetch_source_job", side_effect=RuntimeError("boom")), \
             patch("app.ingestion.service._update_feed_reliability_batch") as mock_batch:
            results = fetch_sources_concurrently(sources, "Technology", topic_id=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "error")
        self.assertEqual(results[0]["source_id"], 1)
        self.assertIn("boom", results[0]["error"])
        mock_batch.assert_called_once_with([], [1])


class LoadActiveTopicGroupsTests(unittest.TestCase):
    def _rows(self, *rows: dict) -> list[dict]:
        return list(rows)

    def test_active_feed_is_included(self) -> None:
        conn, cur = _fake_conn()
        cur.fetchall.return_value = self._rows({
            "topic_id": 1, "topic_name": "Technology", "id": 10, "name": "Reuters",
            "feed_url": "u", "feed_state": "active", "skip_next_run": False,
        })
        with patch("app.ingestion.service.get_connection", return_value=conn):
            groups, suppression = _load_active_topic_groups()

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["sources"][0]["id"], 10)
        self.assertEqual(suppression["suppressed_count"], 0)
        # No suppressed ids -> the reset UPDATE must not run, only the SELECT.
        self.assertEqual(cur.execute.call_count, 1)

    def test_degraded_with_skip_next_run_true_is_suppressed_and_flag_reset(self) -> None:
        conn, cur = _fake_conn()
        cur.fetchall.return_value = self._rows({
            "topic_id": 1, "topic_name": "Technology", "id": 10, "name": "Slow Feed",
            "feed_url": "u", "feed_state": "degraded", "skip_next_run": True,
        })
        with patch("app.ingestion.service.get_connection", return_value=conn):
            groups, suppression = _load_active_topic_groups()

        self.assertEqual(groups, [])
        self.assertEqual(suppression["suppressed_count"], 1)
        self.assertEqual(suppression["suppressed_feeds"][0]["name"], "Slow Feed")
        # Reset UPDATE must run for the suppressed id.
        self.assertEqual(cur.execute.call_count, 2)
        reset_query, reset_params = cur.execute.call_args_list[1][0]
        self.assertIn("skip_next_run = FALSE", reset_query)
        self.assertEqual(reset_params, ([10],))
        conn.commit.assert_called_once()

    def test_degraded_with_skip_next_run_false_is_included(self) -> None:
        conn, cur = _fake_conn()
        cur.fetchall.return_value = self._rows({
            "topic_id": 1, "topic_name": "Technology", "id": 10, "name": "Recovering Feed",
            "feed_url": "u", "feed_state": "degraded", "skip_next_run": False,
        })
        with patch("app.ingestion.service.get_connection", return_value=conn):
            groups, suppression = _load_active_topic_groups()

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["sources"][0]["name"], "Recovering Feed")
        self.assertEqual(suppression["suppressed_count"], 0)

    def test_mixed_feeds_only_suppressed_ones_excluded(self) -> None:
        conn, cur = _fake_conn()
        cur.fetchall.return_value = self._rows(
            {"topic_id": 1, "topic_name": "Technology", "id": 1, "name": "Active",
             "feed_url": "u1", "feed_state": "active", "skip_next_run": False},
            {"topic_id": 1, "topic_name": "Technology", "id": 2, "name": "Suppressed",
             "feed_url": "u2", "feed_state": "degraded", "skip_next_run": True},
        )
        with patch("app.ingestion.service.get_connection", return_value=conn):
            groups, suppression = _load_active_topic_groups()

        included_ids = [s["id"] for s in groups[0]["sources"]]
        self.assertEqual(included_ids, [1])
        self.assertEqual(suppression["suppressed_count"], 1)

    def test_topic_filter_is_passed_through_as_query_param(self) -> None:
        conn, cur = _fake_conn()
        cur.fetchall.return_value = []
        with patch("app.ingestion.service.get_connection", return_value=conn):
            _load_active_topic_groups(topic="Technology")

        query, params = cur.execute.call_args_list[0][0]
        self.assertIn("AND t.name = %s", query)
        self.assertEqual(params, ("Technology",))


if __name__ == "__main__":
    unittest.main()
