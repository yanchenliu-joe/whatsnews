"""Tests for the Phase 26 narrative briefing layer."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.briefing.builder import build_narrative_block, extract_entities
from app.briefing.service import get_daily_briefing


def _event(
    title: str,
    signal_score: int = 80,
    signal_tier: str = "high",
    summary: str = "",
    sources: list | None = None,
    top_articles: list | None = None,
) -> dict:
    return {
        "event_title": title,
        "signal_score": signal_score,
        "signal_tier": signal_tier,
        "summary": summary,
        "sources_count": len(sources or []),
        "sources": sources or [],
        "supporting_article_count": len(top_articles or []) or 1,
        "top_articles": top_articles or [],
    }


class BuildNarrativeBlockTests(unittest.TestCase):
    def test_headline_strips_breaking_prefix_and_caps_at_18_words(self) -> None:
        long_title = "BREAKING: " + " ".join(f"word{i}" for i in range(25))
        block = build_narrative_block(_event(long_title))
        self.assertFalse(block["headline"].startswith("BREAKING"))
        self.assertLessEqual(len(block["headline"].rstrip("…").split()), 18)

    def test_what_happened_attributes_first_sentence_to_source(self) -> None:
        event = _event(
            "Central bank raises rates",
            top_articles=[{"source": "Reuters", "summary": "Rates rose by 50bps."}],
        )
        block = build_narrative_block(event)
        self.assertTrue(block["what_happened"].startswith("According to Reuters:"))

    def test_what_happened_falls_back_to_event_title_without_summaries(self) -> None:
        event = _event("Central bank raises rates", top_articles=[{"source": "Reuters", "summary": ""}])
        block = build_narrative_block(event)
        self.assertEqual(block["what_happened"], "Central bank raises rates")

    def test_why_it_matters_uses_existing_summary_when_substantial(self) -> None:
        event = _event(
            "Central bank raises rates",
            summary="This directly affects millions of borrowers and mortgage holders nationwide.",
        )
        block = build_narrative_block(event)
        self.assertEqual(block["why_it_matters"], event["summary"])

    def test_why_it_matters_falls_back_to_signal_band(self) -> None:
        event = _event("Central bank raises rates", signal_score=95, summary="")
        block = build_narrative_block(event)
        self.assertIn("Exceptional significance", block["why_it_matters"])

    def test_what_changed_detects_acquisition_pattern(self) -> None:
        event = _event("Tech giant acquires rival startup")
        block = build_narrative_block(event)
        self.assertIn("consolidation", block["what_changed"])

    def test_what_changed_detects_numeric_shift_when_no_pattern_matches(self) -> None:
        event = _event("Company reports 42% change in shipment volume")
        block = build_narrative_block(event)
        self.assertIn("quantitative shift", block["what_changed"])

    def test_what_changed_defaults_when_nothing_detected(self) -> None:
        event = _event("A calm and uneventful day in the markets")
        block = build_narrative_block(event)
        self.assertEqual(block["what_changed"], "A notable development has emerged that shifts the prior state.")

    def test_watch_next_matches_keyword_in_title(self) -> None:
        event = _event("Company announces earnings above expectations")
        block = build_narrative_block(event)
        self.assertIn("guidance revisions", block["watch_next"])

    def test_watch_next_falls_back_when_no_match(self) -> None:
        event = _event("A quiet news day")
        block = build_narrative_block(event)
        self.assertIn("follow-on developments", block["watch_next"])

    def test_signal_fields_are_inherited(self) -> None:
        event = _event("Something happened", signal_score=77, signal_tier="high", sources=["Reuters", "AP"])
        block = build_narrative_block(event)
        self.assertEqual(block["signal_score"], 77)
        self.assertEqual(block["signal_tier"], "high")
        self.assertEqual(block["sources_count"], 2)


class ExtractEntitiesTests(unittest.TestCase):
    def test_extracts_proper_nouns_and_acronyms(self) -> None:
        entities = extract_entities(["Apple and NASA announce new partnership in California"])
        self.assertIn("NASA", entities)
        self.assertIn("Apple", entities)
        self.assertIn("California", entities)

    def test_ignores_stop_words(self) -> None:
        entities = extract_entities(["The company is over the moon about this"])
        self.assertNotIn("The", entities)
        self.assertNotIn("This", entities)


class GetDailyBriefingTests(unittest.TestCase):
    def test_unavailable_intelligence_is_passed_through(self) -> None:
        with patch(
            "app.briefing.service.get_daily_intelligence",
            return_value={"available": False, "message": "No report available for this topic and date."},
        ):
            result = get_daily_briefing("Artificial Intelligence")
        self.assertFalse(result["available"])

    def test_no_events_returns_empty_briefing(self) -> None:
        with patch(
            "app.briefing.service.get_daily_intelligence",
            return_value={"available": True, "events": [], "report_date": "2026-07-05", "noise_suppressed_count": 3},
        ):
            result = get_daily_briefing("Artificial Intelligence")
        self.assertTrue(result["available"])
        self.assertEqual(result["briefing"], [])
        self.assertEqual(result["meta"]["noise_suppressed"], 3)

    def test_splits_events_into_primary_and_emerging_tiers(self) -> None:
        events = [
            _event("Primary story", signal_score=85),
            _event("Emerging story", signal_score=55),
        ]
        with patch(
            "app.briefing.service.get_daily_intelligence",
            return_value={
                "available": True,
                "events": events,
                "report_date": "2026-07-05",
                "noise_suppressed_count": 0,
                "signal_summary": {"event_count": 2, "avg_signal_score": 70},
            },
        ):
            result = get_daily_briefing("Artificial Intelligence", include_emerging=True)

        self.assertEqual(len(result["briefing"]), 1)
        self.assertEqual(result["briefing"][0]["headline"], "Primary story")
        self.assertEqual(len(result["emerging_signals"]), 1)
        self.assertEqual(result["emerging_signals"][0]["headline"], "Emerging story")

    def test_include_emerging_false_omits_emerging_signals(self) -> None:
        events = [_event("Emerging story", signal_score=55)]
        with patch(
            "app.briefing.service.get_daily_intelligence",
            return_value={
                "available": True,
                "events": events,
                "report_date": "2026-07-05",
                "noise_suppressed_count": 0,
                "signal_summary": {},
            },
        ):
            result = get_daily_briefing("Artificial Intelligence", include_emerging=False)
        self.assertEqual(result["emerging_signals"], [])

    def test_shared_entity_across_events_forms_a_thread(self) -> None:
        events = [
            _event("Nvidia unveils new chip architecture", signal_score=85),
            _event("Nvidia faces antitrust scrutiny over chip dominance", signal_score=80),
        ]
        with patch(
            "app.briefing.service.get_daily_intelligence",
            return_value={
                "available": True,
                "events": events,
                "report_date": "2026-07-05",
                "noise_suppressed_count": 0,
                "signal_summary": {},
            },
        ):
            result = get_daily_briefing("Technology")
        self.assertEqual(len(result["threads"]), 1)
        self.assertEqual(result["threads"][0]["entity"], "Nvidia")
        self.assertEqual(result["threads"][0]["involved_event_count"], 2)


class DailyBriefingRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self.client = TestClient(main.app)

    def test_route_returns_service_result(self) -> None:
        canned = {"topic": "Artificial Intelligence", "available": True, "briefing": []}
        with patch("app.briefing.routes.get_daily_briefing", return_value=canned):
            response = self.client.get("/daily-briefing", params={"topic": "Artificial Intelligence"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), canned)

    def test_route_returns_503_on_service_error(self) -> None:
        with patch("app.briefing.routes.get_daily_briefing", side_effect=RuntimeError("boom")):
            response = self.client.get("/daily-briefing", params={"topic": "Artificial Intelligence"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
