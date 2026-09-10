"""Tests for the Phase 25 intelligence layer (signal scoring, clustering, service)."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.intelligence.scoring import compute_signal_score
from app.intelligence.clustering import cluster_articles

UTC = ZoneInfo("UTC")
NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def _article(
    title: str,
    hours_ago: float = 1,
    importance_score: int = 0,
    summary: str = "",
    source: str = "Reuters",
) -> dict:
    return {
        "id": abs(hash(title)) % 10_000,
        "title": title,
        "summary": summary,
        "source": source,
        "published_at": NOW - timedelta(hours=hours_ago),
        "editorial_metadata": {"importance_score": importance_score},
        "why_it_matters": "",
    }


class ComputeSignalScoreTests(unittest.TestCase):
    def test_high_impact_recent_reliable_source_scores_high(self) -> None:
        article = _article(
            "Government announces war sanctions on major bank",
            hours_ago=2,
            importance_score=3,
        )
        result = compute_signal_score(article, source_reliability_score=95, now=NOW)

        self.assertEqual(result["novelty_score"], 20)       # < 6h old
        self.assertEqual(result["credibility_score"], 20)    # reliability >= 90
        self.assertEqual(result["impact_score"], 30)         # base 22 + kw_boost capped at 8
        self.assertGreaterEqual(result["signal_score"], 70)
        self.assertEqual(result["signal_tier"], "high")

    def test_stale_low_importance_article_scores_as_noise(self) -> None:
        article = _article(
            "Weekly roundup: things that happened",
            hours_ago=200,
            importance_score=0,
        )
        result = compute_signal_score(article, source_reliability_score=20, now=NOW)

        self.assertEqual(result["novelty_score"], 1)     # > 72h old
        self.assertEqual(result["credibility_score"], 3)  # reliability < 25
        self.assertLess(result["signal_score"], 40)
        self.assertEqual(result["signal_tier"], "noise")

    def test_background_keyword_penalizes_impact_score(self) -> None:
        base = _article("Company launches new product", importance_score=1)
        analysis = _article("Analysis: company launches new product", importance_score=1)

        base_result = compute_signal_score(base, 70, NOW)
        analysis_result = compute_signal_score(analysis, 70, NOW)

        self.assertLess(analysis_result["impact_score"], base_result["impact_score"])

    def test_missing_published_at_gets_default_novelty(self) -> None:
        article = _article("Some headline", importance_score=1)
        article["published_at"] = None
        result = compute_signal_score(article, 70, NOW)
        self.assertEqual(result["novelty_score"], 5)

    def test_signal_tier_boundary_below_40_is_noise(self) -> None:
        # impact=2 (no keywords, importance 0) + novelty=8 (30h old) +
        # credibility=11 (reliability 50) + urgency=6 (30h, no urgency kw) = 27
        article = _article("Routine quarterly filing update", hours_ago=30, importance_score=0)
        result = compute_signal_score(article, source_reliability_score=50, now=NOW)
        self.assertEqual(result["signal_score"], 27)
        self.assertEqual(result["signal_tier"], "noise")


class ClusterArticlesTests(unittest.TestCase):
    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(cluster_articles([]), [])

    def test_top_articles_carry_body_text_through(self) -> None:
        article = _article("Central bank raises interest rates sharply")
        article["signal_score"] = 80
        article["signal_tier"] = "high"
        article["body_text"] = "Full article text here."

        events = cluster_articles([article])

        self.assertEqual(events[0]["top_articles"][0]["body_text"], "Full article text here.")

    def test_single_article_forms_its_own_event(self) -> None:
        article = _article("Central bank raises interest rates sharply")
        article["signal_score"] = 80
        article["signal_tier"] = "high"

        events = cluster_articles([article])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["supporting_article_count"], 1)
        self.assertEqual(events[0]["signal_score"], 80)  # no size bonus for 1 article
        self.assertEqual(events[0]["sources_count"], 1)

    def test_similar_titles_within_window_are_merged(self) -> None:
        lead = _article("Central bank raises interest rates sharply", hours_ago=1, source="Reuters")
        lead["signal_score"] = 80
        lead["signal_tier"] = "high"

        follower = _article("Central bank raises interest rates again", hours_ago=2, source="AP")
        follower["signal_score"] = 60
        follower["signal_tier"] = "high"

        events = cluster_articles([lead, follower])

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["supporting_article_count"], 2)
        self.assertEqual(event["sources_count"], 2)
        # lead (highest signal) score + size-2 bonus (5)
        self.assertEqual(event["signal_score"], 85)
        self.assertEqual(event["event_title"], lead["title"])

    def test_dissimilar_titles_are_not_merged(self) -> None:
        a = _article("Central bank raises interest rates")
        a["signal_score"] = 80
        a["signal_tier"] = "high"
        b = _article("Local sports team wins championship game")
        b["signal_score"] = 75
        b["signal_tier"] = "high"

        events = cluster_articles([a, b])

        self.assertEqual(len(events), 2)

    def test_similar_titles_outside_time_window_are_not_merged(self) -> None:
        a = _article("Central bank raises interest rates sharply", hours_ago=1)
        a["signal_score"] = 80
        a["signal_tier"] = "high"
        b = _article("Central bank raises interest rates again", hours_ago=100)  # > 72h apart
        b["signal_score"] = 60
        b["signal_tier"] = "high"

        events = cluster_articles([a, b])

        self.assertEqual(len(events), 2)

    def test_size_bonus_is_capped_at_100(self) -> None:
        articles = []
        for i in range(6):
            art = _article(f"Central bank raises interest rates variant {i}", hours_ago=1, source=f"Source{i}")
            art["signal_score"] = 98
            art["signal_tier"] = "high"
            articles.append(art)

        events = cluster_articles(articles)

        self.assertEqual(len(events), 1)
        self.assertLessEqual(events[0]["signal_score"], 100)

    def test_events_sorted_by_signal_score_descending(self) -> None:
        low = _article("Local council approves new park", source="Local Times")
        low["signal_score"] = 45
        low["signal_tier"] = "informational"
        high = _article("Major earthquake strikes coastal region", source="Reuters")
        high["signal_score"] = 90
        high["signal_tier"] = "high"

        events = cluster_articles([low, high])

        self.assertEqual(events[0]["event_title"], high["title"])
        self.assertEqual(events[1]["event_title"], low["title"])


def _fake_conn(fetchone_results=None, fetchall_results=None) -> MagicMock:
    """MagicMock connection whose cursor yields queued fetchone/fetchall results in call order."""
    fetchone_queue = list(fetchone_results or [])
    fetchall_queue = list(fetchall_results or [])

    cur = MagicMock()
    cur.fetchone.side_effect = lambda: fetchone_queue.pop(0) if fetchone_queue else None
    cur.fetchall.side_effect = lambda: fetchall_queue.pop(0) if fetchall_queue else []

    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class GetDailyIntelligenceTests(unittest.TestCase):
    def test_no_report_for_date_returns_unavailable(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.intelligence.service.get_connection", return_value=conn):
            result = self._call()
        self.assertFalse(result["available"])

    def test_report_with_no_articles_returns_empty_events(self) -> None:
        conn = _fake_conn(
            fetchone_results=[{"report_id": 1, "topic_id": 10, "topic_name": "Artificial Intelligence"}],
            fetchall_results=[[]],
        )
        with patch("app.intelligence.service.get_connection", return_value=conn):
            result = self._call()

        self.assertTrue(result["available"])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["signal_summary"]["total_articles"], 0)

    def test_report_with_mixed_signal_articles_excludes_noise_from_events(self) -> None:
        high_article = {
            "id": 1, "title": "Central bank announces emergency rate decision",
            "url": "https://example.com/1", "summary": "Breaking economic news.",
            "source": "Reuters", "why_it_matters": "",
            "published_at": NOW - timedelta(hours=1),
            "editorial_metadata": {"importance_score": 3}, "image_url": None,
        }
        noise_article = {
            "id": 2, "title": "Weekly roundup of minor happenings",
            "url": "https://example.com/2", "summary": "",
            "source": "Small Blog", "why_it_matters": "",
            "published_at": NOW - timedelta(hours=200),
            "editorial_metadata": {"importance_score": 0}, "image_url": None,
        }
        report_conn = _fake_conn(
            fetchone_results=[{"report_id": 1, "topic_id": 10, "topic_name": "Markets"}],
            fetchall_results=[[high_article, noise_article]],
        )
        reliability_conn = _fake_conn(fetchall_results=[[{"name": "Reuters", "reliability_score": 95}]])

        with patch(
            "app.intelligence.service.get_connection",
            side_effect=[report_conn, reliability_conn],
        ):
            result = self._call(topic="Markets")

        self.assertTrue(result["available"])
        self.assertEqual(result["signal_summary"]["total_articles"], 2)
        # The noise article should be suppressed from `events`, but counted.
        event_titles = [e["event_title"] for e in result["events"]]
        self.assertIn(high_article["title"], event_titles)
        self.assertNotIn(noise_article["title"], event_titles)
        self.assertGreaterEqual(result["noise_suppressed_count"], 1)

    @staticmethod
    def _call(topic: str = "Artificial Intelligence"):
        from app.intelligence.service import get_daily_intelligence
        return get_daily_intelligence(topic, report_date=NOW.date())


class LoadSourceReliabilityMapTests(unittest.TestCase):
    def test_returns_mapping_from_db_rows(self) -> None:
        conn = _fake_conn(fetchall_results=[[
            {"name": "Reuters", "reliability_score": 95},
            {"name": "Small Blog", "reliability_score": 40},
        ]])
        from app.intelligence.service import _load_source_reliability_map
        with patch("app.intelligence.service.get_connection", return_value=conn):
            result = _load_source_reliability_map()
        self.assertEqual(result, {"Reuters": 95, "Small Blog": 40})

    def test_db_error_returns_empty_dict(self) -> None:
        from app.intelligence.service import _load_source_reliability_map
        with patch("app.intelligence.service.get_connection", side_effect=RuntimeError("db down")):
            result = _load_source_reliability_map()
        self.assertEqual(result, {})


class DailyIntelligenceRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self.client = TestClient(main.app)

    def test_route_returns_service_result(self) -> None:
        canned = {"topic": "Artificial Intelligence", "available": True, "events": []}
        with patch("app.intelligence.routes.get_daily_intelligence", return_value=canned):
            response = self.client.get("/daily-intelligence", params={"topic": "Artificial Intelligence"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), canned)

    def test_route_returns_503_on_service_error(self) -> None:
        with patch("app.intelligence.routes.get_daily_intelligence", side_effect=RuntimeError("boom")):
            response = self.client.get("/daily-intelligence", params={"topic": "Artificial Intelligence"})
        self.assertEqual(response.status_code, 503)


class AdminSignalMetricsRouteTests(unittest.TestCase):
    """
    Regression tests for a real bug found 2026-07-18: this route used
    `_=Depends(require_admin_key)` directly, which made FastAPI treat
    require_admin_key's own `x_admin_key` parameter as a required query
    string parameter (since it has no Header() annotation) instead of
    reading the x-admin-key header every other admin route uses. The key
    still had to be correct to get past it, but it silently ignored the
    documented header entirely, and anyone using it as a query param
    would leak the admin key into access logs/browser history.
    """

    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_open_when_no_admin_key_configured(self) -> None:
        os.environ.pop("ADMIN_API_KEY", None)
        with patch("app.intelligence.routes.get_signal_metrics_for_all_topics", return_value={}):
            response = self.client.get("/admin/signal-metrics")
        self.assertEqual(response.status_code, 200)

    def test_missing_header_returns_401_when_admin_key_configured(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.get("/admin/signal-metrics")
        self.assertEqual(response.status_code, 401)

    def test_wrong_header_returns_401(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.get("/admin/signal-metrics", headers={"x-admin-key": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_correct_header_is_accepted(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        with patch("app.intelligence.routes.get_signal_metrics_for_all_topics", return_value={}):
            response = self.client.get(
                "/admin/signal-metrics", headers={"x-admin-key": "secret"}
            )
        self.assertEqual(response.status_code, 200)

    def test_query_param_alone_is_no_longer_accepted(self) -> None:
        """The old bug's exact symptom — key-as-query-param must not work now."""
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.get("/admin/signal-metrics", params={"x_admin_key": "secret"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
