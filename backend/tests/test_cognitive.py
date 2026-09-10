"""Tests for the Phase 27 cognitive briefing layer."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.cognitive.builder import build_cognitive_block
from app.cognitive.scoring import compute_impact_level, compute_risk_level, compute_confidence
from app.cognitive.service import get_daily_cognitive


def _narrative_block(
    headline: str = "Something happened",
    what_happened: str = "",
    why_it_matters: str = "",
    signal_score: int = 60,
    signal_tier: str = "informational",
    sources_count: int = 1,
    supporting_article_count: int = 1,
    top_articles: list | None = None,
) -> dict:
    return {
        "headline": headline,
        "what_happened": what_happened,
        "why_it_matters": why_it_matters,
        "signal_score": signal_score,
        "signal_tier": signal_tier,
        "sources_count": sources_count,
        "sources": ["Reuters"] * sources_count,
        "supporting_article_count": supporting_article_count,
        "top_articles": top_articles or [],
    }


class ComputeImpactLevelTests(unittest.TestCase):
    def test_bands(self) -> None:
        self.assertEqual(compute_impact_level(80), "critical")
        self.assertEqual(compute_impact_level(79), "high")
        self.assertEqual(compute_impact_level(60), "high")
        self.assertEqual(compute_impact_level(59), "medium")
        self.assertEqual(compute_impact_level(40), "medium")
        self.assertEqual(compute_impact_level(39), "low")


class ComputeRiskLevelTests(unittest.TestCase):
    def test_high_risk_keyword_wins(self) -> None:
        block = _narrative_block(headline="War breaks out, sanctions imposed")
        self.assertEqual(compute_risk_level(block), "high")

    def test_medium_risk_keyword_without_high_risk(self) -> None:
        block = _narrative_block(headline="Regulators launch investigation into fine")
        self.assertEqual(compute_risk_level(block), "medium")

    def test_no_keywords_is_low_risk(self) -> None:
        block = _narrative_block(headline="Company announces new product")
        self.assertEqual(compute_risk_level(block), "low")

    def test_high_risk_beats_medium_risk_when_both_present(self) -> None:
        block = _narrative_block(headline="War and investigation both underway")
        self.assertEqual(compute_risk_level(block), "high")


class ComputeConfidenceTests(unittest.TestCase):
    def test_single_source_single_article_is_baseline(self) -> None:
        block = _narrative_block(sources_count=1, supporting_article_count=1, signal_score=60)
        self.assertEqual(compute_confidence(block), 50)

    def test_more_sources_and_articles_increase_confidence(self) -> None:
        block = _narrative_block(sources_count=4, supporting_article_count=3, signal_score=90)
        # base 50 + source_pts min(45,(4-1)*15=45) + cluster_pts 8 + quality_pts 10 = 113 -> capped 100
        self.assertEqual(compute_confidence(block), 100)

    def test_low_signal_score_reduces_confidence(self) -> None:
        block = _narrative_block(sources_count=1, supporting_article_count=1, signal_score=30)
        # base 50 + 0 + 0 - 10 = 40
        self.assertEqual(compute_confidence(block), 40)

    def test_confidence_floor_is_15(self) -> None:
        block = _narrative_block(sources_count=1, supporting_article_count=1, signal_score=0)
        self.assertGreaterEqual(compute_confidence(block), 15)


class BuildCognitiveBlockTests(unittest.TestCase):
    def test_so_what_uses_interpretive_why_it_matters(self) -> None:
        block = _narrative_block(
            why_it_matters="This directly reshapes how investors price risk across the sector.",
            signal_score=85,
        )
        cognitive = build_cognitive_block(block)
        self.assertEqual(cognitive["so_what"], block["why_it_matters"])

    def test_so_what_falls_back_to_template_for_short_wim(self) -> None:
        block = _narrative_block(why_it_matters="Short.", signal_score=85)
        cognitive = build_cognitive_block(block)
        self.assertIn("consequential", cognitive["so_what"])

    def test_who_is_affected_extracts_known_entities(self) -> None:
        block = _narrative_block(headline="Apple faces new scrutiny from the Federal Reserve in China")
        cognitive = build_cognitive_block(block)
        self.assertIn("Apple", cognitive["who_is_affected"])
        self.assertIn("Federal Reserve", cognitive["who_is_affected"])
        self.assertIn("China", cognitive["who_is_affected"])

    def test_who_is_affected_capped_at_six(self) -> None:
        block = _narrative_block(
            headline="Apple Google Amazon Microsoft Tesla Nvidia Intel all react to China Russia news"
        )
        cognitive = build_cognitive_block(block)
        self.assertLessEqual(len(cognitive["who_is_affected"]), 6)

    def test_action_implication_uses_impact_type_when_present(self) -> None:
        block = _narrative_block(
            signal_score=85,
            top_articles=[{"editorial_metadata": {"impact_types": ["market_moving"]}}],
        )
        cognitive = build_cognitive_block(block)
        self.assertIn("market repricing", cognitive["action_implication"])

    def test_action_implication_falls_back_without_impact_type(self) -> None:
        block = _narrative_block(signal_score=85, top_articles=[{"editorial_metadata": {}}])
        cognitive = build_cognitive_block(block)
        self.assertIn("broad downstream implications", cognitive["action_implication"])

    def test_inherited_fields_pass_through(self) -> None:
        block = _narrative_block(signal_score=77, signal_tier="high", sources_count=3)
        cognitive = build_cognitive_block(block)
        self.assertEqual(cognitive["signal_score"], 77)
        self.assertEqual(cognitive["signal_tier"], "high")
        self.assertEqual(cognitive["sources_count"], 3)
        self.assertEqual(cognitive["impact_level"], compute_impact_level(77))


class GetDailyCognitiveTests(unittest.TestCase):
    def test_unavailable_briefing_is_passed_through(self) -> None:
        with patch(
            "app.cognitive.service.get_daily_briefing",
            return_value={"available": False, "message": "No data available."},
        ):
            result = get_daily_cognitive("Artificial Intelligence")
        self.assertFalse(result["available"])

    def test_enhances_primary_and_emerging_narratives(self) -> None:
        briefing = {
            "topic": "Artificial Intelligence",
            "report_date": "2026-07-05",
            "available": True,
            "briefing": [_narrative_block(headline="Primary story", signal_score=85)],
            "emerging_signals": [_narrative_block(headline="Emerging story", signal_score=55)],
            "threads": [],
            "meta": {},
        }
        with patch("app.cognitive.service.get_daily_briefing", return_value=briefing):
            result = get_daily_cognitive("Artificial Intelligence")

        self.assertTrue(result["available"])
        self.assertEqual(len(result["briefing"]), 1)
        self.assertEqual(result["briefing"][0]["headline"], "Primary story")
        self.assertIn("impact_level", result["briefing"][0])
        self.assertEqual(len(result["emerging_signals"]), 1)
        self.assertIn("cognitive_build_ms", result["meta"])


class DailyCognitiveRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self.client = TestClient(main.app)

    def test_route_returns_service_result(self) -> None:
        canned = {"topic": "Artificial Intelligence", "available": True, "briefing": []}
        with patch("app.cognitive.routes.get_daily_cognitive", return_value=canned):
            response = self.client.get("/daily-cognitive", params={"topic": "Artificial Intelligence"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), canned)

    def test_route_returns_503_on_service_error(self) -> None:
        with patch("app.cognitive.routes.get_daily_cognitive", side_effect=RuntimeError("boom")):
            response = self.client.get("/daily-cognitive", params={"topic": "Artificial Intelligence"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
