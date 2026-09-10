"""Tests for the admin feed-lifecycle endpoints (Phase 24/24.2/25).

Covers /admin/feed-health, /admin/feeds/{id}/test|disable|enable|pause|promote|
replace-mark, and /admin/feed-recommendations, plus the pure scoring helpers
they share. All DB access is mocked — no test touches the real Supabase
instance, and /admin/feeds/{id}/test's external RSS fetch is mocked too.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import app.main as main
from app.ingestion.rss import FeedFetchResult
from app.admin.feed_scoring import (
    _compute_feed_quality_score,
    _compute_topic_health_score,
    _feed_health_status,
    _feed_reliability_score,
)

UTC = ZoneInfo("UTC")
NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def _feed_row(**overrides) -> dict:
    row = {
        "is_active": True,
        "failure_count": 0,
        "success_count": 0,
        "consecutive_failures": 0,
        "consecutive_successes": 0,
        "last_success_at": None,
        "last_failure_at": None,
    }
    row.update(overrides)
    return row


class FeedHealthStatusTests(unittest.TestCase):
    def test_active_no_failures_is_healthy(self) -> None:
        self.assertEqual(_feed_health_status(_feed_row()), "healthy")

    def test_some_consecutive_failures_is_warning(self) -> None:
        self.assertEqual(_feed_health_status(_feed_row(consecutive_failures=2)), "warning")

    def test_five_or_more_consecutive_failures_is_failed(self) -> None:
        self.assertEqual(_feed_health_status(_feed_row(consecutive_failures=5)), "failed")

    def test_inactive_feed_is_failed_regardless_of_failure_count(self) -> None:
        self.assertEqual(_feed_health_status(_feed_row(is_active=False)), "failed")


class FeedReliabilityScoreTests(unittest.TestCase):
    def test_no_history_defaults_to_100(self) -> None:
        self.assertEqual(_feed_reliability_score(_feed_row()), 100)

    def test_computes_success_ratio(self) -> None:
        row = _feed_row(success_count=3, failure_count=1)
        self.assertEqual(_feed_reliability_score(row), 75)


class ComputeFeedQualityScoreTests(unittest.TestCase):
    def test_new_feed_gets_neutral_medium_risk_score(self) -> None:
        result = _compute_feed_quality_score(_feed_row())
        self.assertEqual(result["total"], 70)
        self.assertEqual(result["classification"], "medium_risk")
        self.assertEqual(result["note"], "new_feed_no_history")

    def test_perfect_recent_feed_is_stable(self) -> None:
        row = _feed_row(
            success_count=100, failure_count=0, consecutive_failures=0,
            last_success_at=NOW - timedelta(hours=1),
        )
        with patch("app.admin.feed_scoring.datetime") as mock_dt:
            mock_dt.now.return_value = NOW
            result = _compute_feed_quality_score(row)
        self.assertEqual(result["success_rate_score"], 50)
        self.assertEqual(result["reliability_score"], 30)
        self.assertEqual(result["freshness_score"], 20)
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["classification"], "stable")

    def test_inactive_feed_has_zero_reliability_component(self) -> None:
        row = _feed_row(success_count=10, failure_count=0, is_active=False)
        result = _compute_feed_quality_score(row)
        self.assertEqual(result["reliability_score"], 0)

    def test_chronic_failures_and_stale_feed_is_candidate_for_removal(self) -> None:
        row = _feed_row(
            success_count=2, failure_count=20, consecutive_failures=6,
            last_success_at=NOW - timedelta(days=60),
        )
        with patch("app.admin.feed_scoring.datetime") as mock_dt:
            mock_dt.now.return_value = NOW
            result = _compute_feed_quality_score(row)
        self.assertEqual(result["reliability_score"], 0)
        self.assertEqual(result["freshness_score"], 0)
        self.assertEqual(result["classification"], "candidate_for_removal")

    def test_never_succeeded_has_zero_freshness(self) -> None:
        row = _feed_row(success_count=1, failure_count=1, last_success_at=None)
        result = _compute_feed_quality_score(row)
        self.assertEqual(result["freshness_score"], 0)


class ComputeTopicHealthScoreTests(unittest.TestCase):
    def test_all_feeds_healthy_and_active_articles_is_healthy(self) -> None:
        result = _compute_topic_health_score({"total": 6, "healthy": 6}, recent_article_count=5)
        self.assertEqual(result["classification"], "healthy")
        self.assertEqual(result["total"], 100)

    def test_no_feeds_is_critical_with_zero_score(self) -> None:
        result = _compute_topic_health_score({"total": 0, "healthy": 0}, recent_article_count=0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["classification"], "critical")

    def test_partial_health_is_degraded(self) -> None:
        result = _compute_topic_health_score({"total": 6, "healthy": 2}, recent_article_count=1)
        self.assertEqual(result["classification"], "degraded")


def _fake_conn(fetchone_results=None, fetchall_results=None) -> MagicMock:
    fetchone_queue = list(fetchone_results or [])
    fetchall_queue = list(fetchall_results or [])
    cur = MagicMock()
    cur.fetchone.side_effect = lambda: fetchone_queue.pop(0) if fetchone_queue else None
    cur.fetchall.side_effect = lambda: fetchall_queue.pop(0) if fetchall_queue else []
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class AdminFeedRoutesTestCase(unittest.TestCase):
    """Base class: opens ADMIN_API_KEY so tests focus on business logic, not the gate."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("ADMIN_API_KEY", None)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()


class AdminKeyGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_missing_key_returns_401_when_admin_key_configured(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.get("/admin/feed-health")
        self.assertEqual(response.status_code, 401)

    def test_wrong_key_returns_401(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.post("/admin/feeds/1/disable", headers={"x-admin-key": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_no_admin_key_configured_leaves_endpoint_open(self) -> None:
        os.environ.pop("ADMIN_API_KEY", None)
        conn = _fake_conn(fetchall_results=[[], []])
        with patch("app.admin.feed_diagnostics_routes.get_connection", return_value=conn):
            response = self.client.get("/admin/feed-health")
        self.assertEqual(response.status_code, 200)


class FeedHealthRouteTests(AdminFeedRoutesTestCase):
    def test_groups_feeds_by_topic_with_scores(self) -> None:
        rows = [
            {
                "id": 1, "topic_id": 10, "topic": "Technology", "sort_order": 1,
                "source": "Reuters", "feed_url": "https://example.com/rss",
                "is_active": True, "failure_count": 0, "success_count": 10,
                "consecutive_failures": 0, "consecutive_successes": 10,
                "last_success_at": NOW, "last_failure_at": None, "auto_disabled_at": None,
            },
        ]
        article_counts = [{"topic_id": 10, "recent_article_count": 5}]
        conn = _fake_conn(fetchall_results=[rows, article_counts])
        with patch("app.admin.feed_diagnostics_routes.get_connection", return_value=conn):
            response = self.client.get("/admin/feed-health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["total_feeds"], 1)
        self.assertEqual(body["summary"]["healthy_feeds"], 1)
        self.assertEqual(len(body["topics"]), 1)
        self.assertEqual(body["topics"][0]["topic_name"], "Technology")
        self.assertEqual(body["topics"][0]["feeds"][0]["status"], "healthy")

    def test_missing_database_url_returns_503(self) -> None:
        # get_connection() raises ValueError when DATABASE_URL is unset.
        with patch("app.admin.feed_diagnostics_routes.get_connection", side_effect=ValueError("DATABASE_URL is not set")):
            response = self.client.get("/admin/feed-health")
        self.assertEqual(response.status_code, 503)

    def test_connection_failure_returns_503_not_500(self) -> None:
        # Technical Debt #12 (resolved): a real DB outage (network down, bad
        # credentials) raises psycopg2.OperationalError from get_connection()
        # itself, not ValueError. Before the fix this propagated uncaught as
        # a raw 500; the outer try/except now also catches psycopg2.Error.
        import psycopg2
        with patch(
            "app.admin.feed_diagnostics_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.get("/admin/feed-health")
        self.assertEqual(response.status_code, 503)

    def test_query_error_after_connecting_returns_503(self) -> None:
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("query failed")
        with patch("app.admin.feed_diagnostics_routes.get_connection", return_value=conn):
            response = self.client.get("/admin/feed-health")
        self.assertEqual(response.status_code, 503)


class FeedTestRouteTests(AdminFeedRoutesTestCase):
    def test_successful_fetch_reports_article_count(self) -> None:
        feed_row = {"id": 1, "name": "Reuters", "feed_url": "https://example.com/rss", "is_active": True}
        conn = _fake_conn(fetchone_results=[feed_row])
        fake_result = FeedFetchResult(articles=[{"title": "a"}, {"title": "b"}], status="ok", error=None)
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn), \
             patch("app.admin.feed_lifecycle_routes.fetch_rss_feed_result", return_value=fake_result):
            response = self.client.post("/admin/feeds/1/test")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["article_count"], 2)

    def test_unknown_feed_returns_404(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/999/test")
        self.assertEqual(response.status_code, 404)

    def test_failed_fetch_reports_error(self) -> None:
        feed_row = {"id": 1, "name": "Reuters", "feed_url": "https://example.com/rss", "is_active": True}
        conn = _fake_conn(fetchone_results=[feed_row])
        fake_result = FeedFetchResult(articles=[], status="error", error="timeout")
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn), \
             patch("app.admin.feed_lifecycle_routes.fetch_rss_feed_result", return_value=fake_result):
            response = self.client.post("/admin/feeds/1/test")

        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"], "timeout")


class FeedDisableEnableRouteTests(AdminFeedRoutesTestCase):
    def test_disable_sets_is_active_false(self) -> None:
        conn = _fake_conn(fetchone_results=[{"id": 1, "name": "Reuters"}])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/disable")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"feed_id": 1, "feed_name": "Reuters", "is_active": False})

    def test_disable_unknown_feed_returns_404(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/999/disable")
        self.assertEqual(response.status_code, 404)

    def test_enable_sets_is_active_true(self) -> None:
        conn = _fake_conn(fetchone_results=[{"id": 1, "name": "Reuters"}])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/enable")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"feed_id": 1, "feed_name": "Reuters", "is_active": True})


class FeedPausePromoteRouteTests(AdminFeedRoutesTestCase):
    def test_pause_sets_feed_state_paused(self) -> None:
        conn = _fake_conn(fetchone_results=[{"id": 1, "name": "Reuters", "feed_state": "paused"}])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/pause")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["feed_state"], "paused")

    def test_pause_already_inactive_feed_returns_404(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/pause")
        self.assertEqual(response.status_code, 404)

    def test_promote_sets_feed_state_active(self) -> None:
        conn = _fake_conn(fetchone_results=[{"id": 1, "name": "Reuters", "feed_state": "active"}])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/promote")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["feed_state"], "active")


class FeedReplaceMarkRouteTests(AdminFeedRoutesTestCase):
    def test_marks_feed_for_replacement_with_reason(self) -> None:
        conn = _fake_conn(fetchone_results=[{"id": 1, "name": "Reuters"}])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/replace-mark", json={"reason": "low quality"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["replace_flag"])
        self.assertEqual(body["replace_reason"], "low quality")

    def test_clear_flag_removes_reason(self) -> None:
        conn = _fake_conn(fetchone_results=[{"id": 1, "name": "Reuters"}])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/1/replace-mark", json={"clear": True})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["replace_flag"])
        self.assertIsNone(body["replace_reason"])

    def test_unknown_feed_returns_404(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.admin.feed_lifecycle_routes.get_connection", return_value=conn):
            response = self.client.post("/admin/feeds/999/replace-mark", json={"reason": "x"})
        self.assertEqual(response.status_code, 404)


class FeedRecommendationsRouteTests(AdminFeedRoutesTestCase):
    def test_classifies_chronic_failure_feed_as_to_disable(self) -> None:
        feeds = [{
            "id": 1, "topic": "Technology", "source": "Dead Blog",
            "feed_url": "https://example.com/dead", "is_active": True, "feed_state": "active",
            "failure_count": 20, "success_count": 1, "consecutive_failures": 6,
            "last_success_at": NOW - timedelta(days=30), "last_failure_at": NOW,
            "replace_flag": False, "replace_reason": None,
        }]
        conn = _fake_conn(fetchall_results=[feeds, [], []])
        with patch("app.admin.feed_recommendation_routes.get_connection", return_value=conn), \
             patch("app.admin.feed_recommendation_routes.datetime") as mock_dt:
            mock_dt.now.return_value = NOW
            response = self.client.get("/admin/feed-recommendations")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["to_disable_count"], 1)
        self.assertEqual(body["to_disable"][0]["reason"], "chronic_failure_no_recent_success")

    def test_classifies_high_quality_stable_feed_as_high_value(self) -> None:
        feeds = [{
            "id": 2, "topic": "Technology", "source": "Reuters",
            "feed_url": "https://example.com/reuters", "is_active": True, "feed_state": "active",
            "failure_count": 0, "success_count": 100, "consecutive_failures": 0,
            "last_success_at": NOW - timedelta(hours=1), "last_failure_at": None,
            "replace_flag": False, "replace_reason": None,
        }]
        conn = _fake_conn(fetchall_results=[feeds, [{"source": "Reuters", "topic": "Technology", "article_count": 50}],
                                            [{"topic": "Technology", "total": 100}]])
        with patch("app.admin.feed_recommendation_routes.get_connection", return_value=conn), \
             patch("app.admin.feed_recommendation_routes.datetime") as mock_dt, \
             patch("app.admin.feed_scoring.datetime") as mock_dt2:
            mock_dt.now.return_value = NOW
            mock_dt2.now.return_value = NOW
            response = self.client.get("/admin/feed-recommendations")

        body = response.json()
        self.assertEqual(body["summary"]["high_value_count"], 1)
        self.assertEqual(body["summary"]["to_promote_count"], 1)

    def test_missing_database_url_returns_503(self) -> None:
        with patch("app.admin.feed_recommendation_routes.get_connection", side_effect=ValueError("DATABASE_URL is not set")):
            response = self.client.get("/admin/feed-recommendations")
        self.assertEqual(response.status_code, 503)

    def test_connection_failure_returns_503_not_500(self) -> None:
        # Technical Debt #12 (resolved) — see the matching test on
        # FeedHealthRouteTests above for the full explanation.
        import psycopg2
        with patch(
            "app.admin.feed_recommendation_routes.get_connection",
            side_effect=psycopg2.OperationalError("could not connect to server"),
        ):
            response = self.client.get("/admin/feed-recommendations")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
