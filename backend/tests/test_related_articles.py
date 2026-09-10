"""Tests for the Phase 31 related-articles feature (entity/keyword overlap matching).

No embeddings, no new tables — pure Python scoring over a DB-mocked candidate
pool. No test hits the real Supabase instance.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.related.matching import extract_query_signature, score_candidate
from app.related.service import get_related_articles

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)


class ScoreCandidateTests(unittest.TestCase):
    def test_shared_entity_and_topic_scores_highest(self) -> None:
        q_ent, q_tok = extract_query_signature("Nvidia unveils new chip architecture for AI data centers")
        score = score_candidate(q_ent, q_tok, "Technology", "Nvidia faces antitrust scrutiny over chip dominance", "Technology")
        self.assertGreater(score, 10)  # entity match (10) + topic bonus (1) + some jaccard

    def test_completely_unrelated_scores_zero(self) -> None:
        q_ent, q_tok = extract_query_signature("Nvidia unveils new chip architecture for AI data centers")
        score = score_candidate(q_ent, q_tok, "Technology", "Local sports team wins championship game", "Sports")
        self.assertEqual(score, 0.0)

    def test_shared_entity_without_matching_topic_still_scores(self) -> None:
        q_ent, q_tok = extract_query_signature("Nvidia unveils new chip architecture")
        score = score_candidate(q_ent, q_tok, "Technology", "Nvidia stock surges after earnings beat", "Markets")
        self.assertGreaterEqual(score, 10)  # entity match, no topic bonus since topics differ

    def test_no_shared_entity_but_title_overlap_still_scores_low_positive(self) -> None:
        q_ent, q_tok = extract_query_signature("Central bank raises interest rates sharply")
        score = score_candidate(q_ent, q_tok, "Markets", "Bank raises rates again this quarter", "Markets")
        self.assertGreater(score, 0)
        self.assertLess(score, 10)  # no entity match (10-pt jump), just jaccard + topic bonus


class GetRelatedArticlesTests(unittest.TestCase):
    def _candidate(self, title: str, topic_name: str, hours_ago: float = 1, url: str = None) -> dict:
        return {
            "id": abs(hash(title)) % 10_000,
            "title": title,
            "summary": "",
            "why_it_matters": "",
            "source": "Reuters",
            "url": url or f"https://example.com/{abs(hash(title))}",
            "published_at": NOW - timedelta(hours=hours_ago),
            "image_url": None,
            "topic_name": topic_name,
        }

    def test_returns_empty_list_when_nothing_matches(self) -> None:
        candidates = [self._candidate("Local sports team wins championship game", "Sports")]
        with patch("app.related.service.fetch_candidate_articles", return_value=candidates):
            result = get_related_articles("Nvidia unveils new chip architecture", "Technology", None, limit=5)
        self.assertEqual(result, [])

    def test_returns_matches_sorted_by_score_then_recency(self) -> None:
        candidates = [
            self._candidate("Nvidia stock dips slightly on market news", "Markets", hours_ago=50),
            self._candidate("Nvidia unveils competing chip architecture for data centers", "Technology", hours_ago=2),
            self._candidate("Local sports team wins championship game", "Sports", hours_ago=1),
        ]
        with patch("app.related.service.fetch_candidate_articles", return_value=candidates):
            result = get_related_articles("Nvidia unveils new chip architecture for AI", "Technology", None, limit=5)

        self.assertEqual(len(result), 2)  # sports article excluded — zero score
        self.assertIn("Nvidia", result[0]["title"])  # same-topic, higher overlap ranks first

    def test_respects_limit(self) -> None:
        candidates = [
            self._candidate(f"Nvidia chip announcement number {i}", "Technology", hours_ago=i)
            for i in range(10)
        ]
        with patch("app.related.service.fetch_candidate_articles", return_value=candidates):
            result = get_related_articles("Nvidia chip announcement", "Technology", None, limit=3)
        self.assertEqual(len(result), 3)

    def test_item_shape_matches_expected_fields(self) -> None:
        candidates = [self._candidate("Nvidia unveils new chip architecture", "Technology")]
        with patch("app.related.service.fetch_candidate_articles", return_value=candidates):
            result = get_related_articles("Nvidia unveils new chip architecture", "Technology", None, limit=5)
        self.assertEqual(len(result), 1)
        item = result[0]
        for key in ("title", "summary", "why_it_matters", "source", "url", "image_url", "published_at", "topic"):
            self.assertIn(key, item)

    def test_exclude_url_is_passed_through_to_repository(self) -> None:
        with patch("app.related.service.fetch_candidate_articles", return_value=[]) as mock_fetch:
            get_related_articles("Some title", "Technology", "https://example.com/self", limit=5)
        mock_fetch.assert_called_once_with(exclude_url="https://example.com/self", days=7, pool_limit=500)


class ArticlesRelatedRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self.client = TestClient(main.app)

    def test_route_returns_items(self) -> None:
        canned = [{"title": "Related story", "summary": "", "why_it_matters": "", "source": "Reuters",
                   "url": "https://example.com/b", "image_url": None, "published_at": None, "topic": "Technology"}]
        with patch("app.related.routes.get_related_articles", return_value=canned):
            response = self.client.get(
                "/articles/related",
                params={"title": "Nvidia unveils new chip", "topic": "Technology", "exclude_url": "https://example.com/a"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": canned})

    def test_route_requires_title(self) -> None:
        response = self.client.get("/articles/related")
        self.assertEqual(response.status_code, 422)

    def test_route_returns_503_on_service_error(self) -> None:
        with patch("app.related.routes.get_related_articles", side_effect=RuntimeError("db down")):
            response = self.client.get("/articles/related", params={"title": "Some title"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
