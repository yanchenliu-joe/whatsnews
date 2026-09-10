"""Tests for the Phase 28/28B unified feed layer."""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.feed import normalizer
from app.feed.service import (
    _build_fallback_chain,
    _resolve_mode,
    _select_mode,
    clear_feed_cache,
    get_auto_feed,
    get_daily_feed,
)

UTC = ZoneInfo("UTC")
TODAY = date(2026, 7, 5)


class NormalizeRawTests(unittest.TestCase):
    def test_maps_article_fields_to_unified_schema(self) -> None:
        data = {
            "articles": [{
                "title": "Headline text",
                "summary": "Summary text",
                "source": "Reuters",
                "why_it_matters": "Because reasons.",
                "published_at": datetime(2026, 7, 5, 8, tzinfo=UTC),
                "url": "https://example.com/a",
                "image_url": "https://example.com/a.png",
                "topic_name": "Technology",
            }],
        }
        items = normalizer.normalize_raw(data)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["headline"], "Headline text")
        self.assertEqual(item["so_what"], "Because reasons.")
        self.assertEqual(item["sources"], ["Reuters"])
        self.assertEqual(item["sources_count"], 1)
        self.assertEqual(item["published_at"], "2026-07-05T08:00:00+00:00")
        self.assertEqual(item["topic"], "Technology")

    def test_empty_articles_returns_empty_list(self) -> None:
        self.assertEqual(normalizer.normalize_raw({"articles": []}), [])


class NormalizeSignalTests(unittest.TestCase):
    def test_maps_event_fields(self) -> None:
        data = {"events": [{
            "event_title": "Central bank raises rates",
            "summary": "Rates rose.",
            "signal_score": 82,
            "sources": ["Reuters", "AP"],
            "sources_count": 2,
            "top_articles": [{"published_at": "2026-07-05T08:00:00+00:00"}],
        }]}
        items = normalizer.normalize_signal(data)
        self.assertEqual(items[0]["headline"], "Central bank raises rates")
        self.assertEqual(items[0]["signal_score"], 82)
        self.assertEqual(items[0]["sources_count"], 2)
        self.assertEqual(items[0]["published_at"], "2026-07-05T08:00:00+00:00")


class NormalizeBriefingTests(unittest.TestCase):
    def test_combines_primary_and_emerging(self) -> None:
        data = {
            "briefing": [{"headline": "Primary", "what_happened": "X happened", "why_it_matters": "It matters",
                          "signal_score": 85, "sources": ["Reuters"], "sources_count": 1, "top_articles": []}],
            "emerging_signals": [{"headline": "Emerging", "what_happened": "Y happened", "why_it_matters": "",
                                   "signal_score": 55, "sources": [], "sources_count": 0, "top_articles": []}],
        }
        items = normalizer.normalize_briefing(data)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["headline"], "Primary")
        self.assertEqual(items[0]["so_what"], "It matters")
        self.assertEqual(items[1]["headline"], "Emerging")

    def test_carries_body_text_from_lead_article(self) -> None:
        data = {
            "briefing": [{
                "headline": "Primary", "what_happened": "X happened", "why_it_matters": "It matters",
                "signal_score": 85, "sources": ["Reuters"], "sources_count": 1,
                "top_articles": [{"body_text": "Full article text here."}],
            }],
            "emerging_signals": [],
        }
        items = normalizer.normalize_briefing(data)
        self.assertEqual(items[0]["body_text"], "Full article text here.")


class NormalizeCognitiveTests(unittest.TestCase):
    def test_maps_cognitive_fields(self) -> None:
        data = {"briefing": [{
            "headline": "Primary", "what_happened": "X happened", "so_what": "Why it matters",
            "impact_level": "high", "risk_level": "medium", "confidence": 80,
            "signal_score": 85, "sources": ["Reuters"], "sources_count": 1, "top_articles": [],
        }], "emerging_signals": []}
        items = normalizer.normalize_cognitive(data)
        self.assertEqual(items[0]["impact_level"], "high")
        self.assertEqual(items[0]["risk_level"], "medium")
        self.assertEqual(items[0]["confidence"], 80)

    def test_carries_body_text_from_lead_article(self) -> None:
        data = {"briefing": [{
            "headline": "Primary", "what_happened": "X happened", "so_what": "Why it matters",
            "impact_level": "high", "risk_level": "medium", "confidence": 80,
            "signal_score": 85, "sources": ["Reuters"], "sources_count": 1,
            "top_articles": [{"body_text": "Full article text here."}],
        }], "emerging_signals": []}
        items = normalizer.normalize_cognitive(data)
        self.assertEqual(items[0]["body_text"], "Full article text here.")


class ResolveModeTests(unittest.TestCase):
    def test_auto_expands_to_cognitive(self) -> None:
        self.assertEqual(_resolve_mode("auto"), "cognitive")

    def test_explicit_mode_passes_through(self) -> None:
        for mode in ("raw", "signal", "briefing", "cognitive"):
            self.assertEqual(_resolve_mode(mode), mode)


class BuildFallbackChainTests(unittest.TestCase):
    def test_selected_mode_is_first_then_remaining_chain_order(self) -> None:
        self.assertEqual(_build_fallback_chain("briefing"), ["briefing", "cognitive", "signal", "raw"])
        self.assertEqual(_build_fallback_chain("raw"), ["raw", "cognitive", "briefing", "signal"])

    def test_no_duplicate_of_selected_mode(self) -> None:
        chain = _build_fallback_chain("cognitive")
        self.assertEqual(chain.count("cognitive"), 1)


class SelectModeTests(unittest.TestCase):
    def test_mobile_client_type_header_wins(self) -> None:
        mode, reason = _select_mode("Technology", user_agent="curl/8.0", client_type="mobile")
        self.assertEqual(mode, "cognitive")
        self.assertIn("X-Client-Type", reason)

    def test_investor_topic_forces_cognitive_regardless_of_client(self) -> None:
        mode, reason = _select_mode("Markets", user_agent=None, client_type=None)
        self.assertEqual(mode, "cognitive")
        self.assertIn("Investor-grade", reason)

    def test_mobile_user_agent_selects_cognitive(self) -> None:
        mode, _ = _select_mode(
            "Technology",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            client_type=None,
        )
        self.assertEqual(mode, "cognitive")

    def test_desktop_user_agent_selects_briefing(self) -> None:
        mode, _ = _select_mode(
            "Technology",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            client_type=None,
        )
        self.assertEqual(mode, "briefing")

    def test_no_hints_defaults_to_briefing(self) -> None:
        mode, _ = _select_mode("Technology", user_agent=None, client_type=None)
        self.assertEqual(mode, "briefing")


def _fake_conn(fetchone_results=None, fetchall_results=None) -> MagicMock:
    fetchone_queue = list(fetchone_results or [])
    fetchall_queue = list(fetchall_results or [])
    cur = MagicMock()
    cur.fetchone.side_effect = lambda: fetchone_queue.pop(0) if fetchone_queue else None
    cur.fetchall.side_effect = lambda: fetchall_queue.pop(0) if fetchall_queue else []
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class GetDailyFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_feed_cache()

    def test_invalid_mode_returns_error_dict(self) -> None:
        result = get_daily_feed("Technology", mode="bogus")
        self.assertIn("error", result)

    def test_briefing_mode_dispatches_to_briefing_service(self) -> None:
        canned = {"available": True, "topic": "Technology", "briefing": [], "emerging_signals": [], "report_date": "2026-07-05"}
        with patch("app.feed.service.get_daily_briefing", return_value=canned) as mock_briefing:
            result = get_daily_feed("Technology", mode="briefing", report_date=TODAY)
        mock_briefing.assert_called_once()
        self.assertEqual(result["mode_used"], "briefing")
        self.assertEqual(result["items"], [])

    def test_auto_mode_resolves_to_cognitive(self) -> None:
        canned = {"available": True, "topic": "Technology", "briefing": [], "emerging_signals": [], "report_date": "2026-07-05"}
        with patch("app.feed.service.get_daily_cognitive", return_value=canned):
            result = get_daily_feed("Technology", mode="auto", report_date=TODAY)
        self.assertEqual(result["mode_used"], "cognitive")


class GetAutoFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_feed_cache()

    def test_selected_mode_returns_items_no_fallback(self) -> None:
        cognitive_data = {
            "available": True, "topic": "Markets", "report_date": "2026-07-05",
            "briefing": [{"headline": "Story", "what_happened": "", "so_what": "", "impact_level": "high",
                          "risk_level": "low", "confidence": 70, "signal_score": 80,
                          "sources": ["Reuters"], "sources_count": 1, "top_articles": []}],
            "emerging_signals": [],
        }
        with patch("app.feed.service.get_daily_cognitive", return_value=cognitive_data) as mock_cog:
            result = get_auto_feed("Markets", report_date=TODAY, user_agent=None, client_type=None)

        mock_cog.assert_called_once()
        self.assertEqual(result["mode_used"], "cognitive")
        self.assertFalse(result["meta"]["fallback_applied"])
        self.assertEqual(len(result["items"]), 1)

    def test_falls_back_when_selected_mode_returns_zero_items(self) -> None:
        empty = {"available": True, "topic": "Technology", "report_date": "2026-07-05", "briefing": [], "emerging_signals": []}
        raw_data = {
            "available": True, "topic": "Technology", "report_date": "2026-07-05",
            "articles": [{"title": "Raw article", "summary": "", "source": "AP",
                          "why_it_matters": "", "published_at": None, "url": None,
                          "image_url": None, "topic_name": "Technology"}],
        }
        with patch("app.feed.service.get_daily_briefing", return_value=empty), \
             patch("app.feed.service.get_daily_cognitive", return_value=empty), \
             patch("app.feed.service.get_daily_intelligence", return_value=empty), \
             patch("app.feed.service._get_raw_articles", return_value=raw_data):
            result = get_auto_feed(
                "Technology",
                report_date=TODAY,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                client_type=None,
            )

        self.assertEqual(result["mode_used"], "raw")
        self.assertTrue(result["meta"]["fallback_applied"])
        self.assertEqual(result["meta"]["mode_selected"], "briefing")
        self.assertEqual(len(result["items"]), 1)

    def test_second_call_is_served_from_cache(self) -> None:
        cognitive_data = {
            "available": True, "topic": "Markets", "report_date": "2026-07-05",
            "briefing": [{"headline": "Story", "what_happened": "", "so_what": "", "impact_level": "high",
                          "risk_level": "low", "confidence": 70, "signal_score": 80,
                          "sources": ["Reuters"], "sources_count": 1, "top_articles": []}],
            "emerging_signals": [],
        }
        with patch("app.feed.service.get_daily_cognitive", return_value=cognitive_data) as mock_cog:
            get_auto_feed("Markets", report_date=TODAY, user_agent=None, client_type=None)
            result2 = get_auto_feed("Markets", report_date=TODAY, user_agent=None, client_type=None)

        mock_cog.assert_called_once()  # second call hit cache, no second compute
        self.assertTrue(result2["meta"]["cache_hit"])

    def test_all_topics_mode_skips_selection_and_uses_raw(self) -> None:
        all_data = {
            "available": True, "topic": "All", "report_date": "2026-07-05",
            "articles": [{"title": "Cross-topic article", "summary": "", "source": "AP",
                          "why_it_matters": "", "published_at": None, "url": None,
                          "image_url": None, "topic_name": "Technology"}],
        }
        with patch("app.feed.service._get_all_topics_articles", return_value=all_data):
            result = get_auto_feed("All", report_date=TODAY)
        self.assertEqual(result["mode_used"], "raw")
        self.assertEqual(len(result["items"]), 1)

    def test_all_fallback_modes_empty_returns_unavailable(self) -> None:
        empty = {"available": False, "topic": "Technology", "briefing": [], "emerging_signals": [], "articles": []}
        with patch("app.feed.service.get_daily_briefing", return_value=empty), \
             patch("app.feed.service.get_daily_cognitive", return_value=empty), \
             patch("app.feed.service.get_daily_intelligence", return_value=empty), \
             patch("app.feed.service._get_raw_articles", return_value=empty):
            result = get_auto_feed("Technology", report_date=TODAY, user_agent=None, client_type=None)
        self.assertFalse(result["available"])
        self.assertEqual(result["items"], [])


class ResolveReportDateTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_feed_cache()

    def test_explicit_date_is_returned_as_is(self) -> None:
        from app.feed.service import _resolve_report_date
        resolved, fallback = _resolve_report_date("Technology", TODAY)
        self.assertEqual(resolved, TODAY)
        self.assertFalse(fallback)

    def test_missing_date_queries_latest_from_db(self) -> None:
        from app.feed.service import _resolve_report_date
        conn = _fake_conn(fetchone_results=[{"latest": TODAY}])
        with patch("app.feed.service.get_connection", return_value=conn):
            resolved, fallback = _resolve_report_date("Technology", None)
        self.assertEqual(resolved, TODAY)
        self.assertTrue(fallback)


class ClearFeedCacheTests(unittest.TestCase):
    def test_returns_count_of_cleared_entries(self) -> None:
        cognitive_data = {
            "available": True, "topic": "Markets", "report_date": "2026-07-05",
            "briefing": [{"headline": "Story", "what_happened": "", "so_what": "", "impact_level": "high",
                          "risk_level": "low", "confidence": 70, "signal_score": 80,
                          "sources": ["Reuters"], "sources_count": 1, "top_articles": []}],
            "emerging_signals": [],
        }
        clear_feed_cache()
        with patch("app.feed.service.get_daily_cognitive", return_value=cognitive_data):
            get_auto_feed("Markets", report_date=TODAY, user_agent=None, client_type=None)
        cleared = clear_feed_cache()
        self.assertGreaterEqual(cleared, 1)
        self.assertEqual(clear_feed_cache(), 0)


class FeedRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        clear_feed_cache()
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("ADMIN_API_KEY", None)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_feed_route_passes_client_type_header(self) -> None:
        canned = {"topic": "Technology", "mode_used": "cognitive", "available": True, "items": [], "meta": {}}
        with patch("app.feed.routes.get_auto_feed", return_value=canned) as mock_auto:
            response = self.client.get(
                "/feed", params={"topic": "Technology"}, headers={"X-Client-Type": "mobile"}
            )
        self.assertEqual(response.status_code, 200)
        _, kwargs = mock_auto.call_args
        self.assertEqual(kwargs["client_type"], "mobile")

    def test_daily_feed_route_rejects_invalid_mode(self) -> None:
        response = self.client.get("/daily-feed", params={"topic": "Technology", "mode": "bogus"})
        self.assertEqual(response.status_code, 400)

    def test_feed_cache_clear_route(self) -> None:
        response = self.client.post("/admin/feed/cache/clear")
        self.assertEqual(response.status_code, 200)
        self.assertIn("cleared", response.json())

    def test_feed_cache_clear_requires_admin_key_when_configured(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.post("/admin/feed/cache/clear")
        self.assertEqual(response.status_code, 401)

    def test_feed_cache_clear_rejects_wrong_admin_key(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.post("/admin/feed/cache/clear", headers={"x-admin-key": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_feed_cache_clear_accepts_correct_admin_key(self) -> None:
        os.environ["ADMIN_API_KEY"] = "secret"
        response = self.client.post("/admin/feed/cache/clear", headers={"x-admin-key": "secret"})
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
