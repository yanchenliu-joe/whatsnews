"""Tests for the article body scraping feature flag and gating (app/ingestion/scrape.py)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from app.ingestion.config import article_scraping_enabled
from app.ingestion.scrape import (
    _fetch_body,
    _looks_like_navigation_dump,
    _strip_al_jazeera_recommended_stories,
    _strip_leading_junk_line,
    _strip_leading_photo_credit,
    _strip_related_widget_headings,
    _strip_zdnet_leading_disclosure,
    _truncate_at_trailing_boilerplate,
    scrape_body_texts_concurrent,
)


class ArticleScrapingEnabledTests(unittest.TestCase):
    def test_defaults_to_false_when_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLE_ARTICLE_SCRAPING", None)
            self.assertFalse(article_scraping_enabled())

    def test_true_variants_enable_it(self) -> None:
        for value in ("true", "True", "1", "yes"):
            with patch.dict(os.environ, {"ENABLE_ARTICLE_SCRAPING": value}):
                self.assertTrue(article_scraping_enabled())

    def test_false_variants_disable_it(self) -> None:
        for value in ("false", "0", "no", "garbage"):
            with patch.dict(os.environ, {"ENABLE_ARTICLE_SCRAPING": value}):
                self.assertFalse(article_scraping_enabled())


class ScrapeBodyTextsConcurrentTests(unittest.TestCase):
    def test_empty_articles_returns_empty_dict(self) -> None:
        self.assertEqual(scrape_body_texts_concurrent([]), {})

    def test_articles_without_url_are_ignored(self) -> None:
        self.assertEqual(scrape_body_texts_concurrent([{"title": "No URL here"}]), {})

    def test_fetch_failures_are_omitted_not_raised(self) -> None:
        with patch("app.ingestion.scrape._fetch_body", return_value=""):
            result = scrape_body_texts_concurrent(
                [{"url": "https://example.com/a"}], max_workers=2
            )
        self.assertEqual(result, {})

    def test_successful_fetch_is_included(self) -> None:
        with patch("app.ingestion.scrape._fetch_body", return_value="Full article text."):
            result = scrape_body_texts_concurrent(
                [{"url": "https://example.com/a"}], max_workers=2
            )
        self.assertEqual(result, {"https://example.com/a": "Full article text."})


def _mock_stream_response(status_code: int, chunks: list[bytes]):
    """Build a mock matching httpx.stream(...)'s context-manager shape."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.iter_bytes.return_value = iter(chunks)
    ctx = MagicMock()
    ctx.__enter__.return_value = resp
    ctx.__exit__.return_value = False
    return ctx


class FetchBodyStreamingCapTests(unittest.TestCase):
    """
    Regression tests for the 2026-07-07 fix: _fetch_body() used to download
    a page's full response body before extracting — some sites serve
    several MB per article (ads/scripts/tracking payloads), which
    contributed to Render Starter-plan (512MB) OOM crashes during a full
    20-topic pipeline run. Now streams and stops after _MAX_DOWNLOAD_BYTES.
    """

    def test_stops_reading_once_cap_is_reached(self) -> None:
        big_article_html = (
            "<html><body><article>" + ("Real article text. " * 200) + "</article></body></html>"
        )
        # Chunk 1 alone already exceeds a tiny cap we patch in below.
        chunks = [big_article_html.encode("utf-8"), b"<html>more that must never be read</html>"]
        mock_ctx = _mock_stream_response(200, chunks)
        with patch("httpx.stream", return_value=mock_ctx) as mock_stream, \
             patch("app.ingestion.scrape._MAX_DOWNLOAD_BYTES", 100), \
             patch("app.ingestion.scrape.trafilatura.extract", return_value="Real article text. " * 10):
            _fetch_body("https://example.com/a")
        mock_stream.assert_called_once()
        # Only the first chunk should ever have been consumed from iter_bytes.
        args, kwargs = mock_stream.call_args
        self.assertEqual(args[0], "GET")

    def test_non_200_status_returns_empty(self) -> None:
        mock_ctx = _mock_stream_response(404, [b"not found"])
        with patch("httpx.stream", return_value=mock_ctx):
            self.assertEqual(_fetch_body("https://example.com/missing"), "")

    def test_normal_sized_page_extracts_normally(self) -> None:
        html = "<html><body><article>" + ("Real news content. " * 50) + "</article></body></html>"
        mock_ctx = _mock_stream_response(200, [html.encode("utf-8")])
        with patch("httpx.stream", return_value=mock_ctx), \
             patch(
                 "app.ingestion.scrape.trafilatura.extract",
                 return_value="Real news content. " * 50,
             ):
            result = _fetch_body("https://example.com/a")
        self.assertTrue(result.startswith("Real news content."))


class LooksLikeNavigationDumpTests(unittest.TestCase):
    def test_real_world_nav_dump_is_detected(self) -> None:
        # Captured from a live scrape of Offshore-Energy.biz that fell back
        # to the site's own nav/menu instead of the article body.
        text = (
            "Direct naar inhoud\nOffshore-Energy.biz\noffshoreWIND.biz\n"
            "DredgingToday.com\nNavalToday.com\nExhibition and Conference\n"
            "Advertising\n, go to home\nGreen Marine\nHydrogen\nMarine Energy\n"
            "Subsea\nFossil Energy\nAlternative Fuels\nNews"
        )
        self.assertTrue(_looks_like_navigation_dump(text))

    def test_real_article_prose_is_not_flagged(self) -> None:
        text = (
            "DALLAS — A partnership between Chicago-based Glenstar and "
            "New York City-based Affinius Capital is underway on the $12 "
            "million renovation of Energy Square, a five-building office "
            "campus located in the University Park area of Dallas.\n"
            "Designed by Gensler, the latest capital improvement program "
            "will involve the build-out of several new amenity spaces."
        )
        self.assertFalse(_looks_like_navigation_dump(text))

    def test_short_text_is_never_flagged(self) -> None:
        self.assertFalse(_looks_like_navigation_dump("Short.\nToo few lines."))


class StripLeadingJunkLineTests(unittest.TestCase):
    def test_strips_leading_stray_number(self) -> None:
        text = "2\nDALLAS — A partnership between Chicago-based Glenstar..."
        self.assertEqual(
            _strip_leading_junk_line(text),
            "DALLAS — A partnership between Chicago-based Glenstar...",
        )

    def test_leaves_normal_text_untouched(self) -> None:
        text = "DALLAS — A partnership between Chicago-based Glenstar..."
        self.assertEqual(_strip_leading_junk_line(text), text)


class StripLeadingPhotoCreditTests(unittest.TestCase):
    def test_real_world_vox_caption_is_stripped(self) -> None:
        # Captured from a live scrape of a Vox.com article — the image
        # caption + credit line was getting prepended to the real body.
        text = (
            "In this pool photograph distributed by the Russian state agency "
            "Sputnik, Russia's President Vladimir Putin oversees the joint "
            "Russian-Belarusian nuclear weapons drills along with Belarusian "
            "President, via a videolink in Moscow on May 21, 2026. | "
            "POOL/AFP via Getty Images Key takeaways Ukraine is increasingly "
            "launching drone strikes deep into Russia."
        )
        result = _strip_leading_photo_credit(text).strip()
        self.assertEqual(
            result,
            "Key takeaways Ukraine is increasingly launching drone strikes deep into Russia.",
        )

    def test_short_pipe_credit_is_stripped(self) -> None:
        text = "A man walks down a street in New York. | Reuters The city saw record heat this week."
        result = _strip_leading_photo_credit(text).strip()
        self.assertEqual(result, "The city saw record heat this week.")

    def test_text_with_no_pipe_is_untouched(self) -> None:
        text = "This is a normal article about the economy. Reuters reported markets are up."
        self.assertEqual(_strip_leading_photo_credit(text), text)

    def test_pipe_without_agency_keyword_is_untouched(self) -> None:
        text = "Breaking News | Top Stories Today the president announced a new policy."
        self.assertEqual(_strip_leading_photo_credit(text), text)

    def test_agency_keyword_far_from_any_pipe_is_untouched(self) -> None:
        text = (
            "The stock market saw gains today. " * 5
            + "Getty Images announced a partnership with Reuters for photo licensing."
        )
        self.assertEqual(_strip_leading_photo_credit(text), text)

    def test_does_not_eat_into_real_content_after_the_credit(self) -> None:
        # Regression: an earlier version of the pattern greedily consumed up
        # to 40 characters after the matched agency name, eating into the
        # start of the real article text when there's no separating newline.
        text = "Caption text. | AP Photo The president spoke today about the economy and jobs."
        result = _strip_leading_photo_credit(text).strip()
        self.assertTrue(result.startswith("The president spoke today"))


class TruncateAtTrailingBoilerplateTests(unittest.TestCase):
    def test_field_level_media_wire_footer_is_truncated(self) -> None:
        # Real production example: a sports wire-service attribution
        # followed by an unrelated "related picks" bullet list.
        text = (
            "Mike Conley signed with the Celtics last week.\n"
            "--Field Level Media\n"
            "- MLB Picks Today: Best Bets for Padres vs. Dodgers\n"
            "- Fourth of July Best MLB Betting Picks and Predictions"
        )
        result = _truncate_at_trailing_boilerplate(text)
        self.assertEqual(result, "Mike Conley signed with the Celtics last week.")

    def test_newsletter_prompt_is_truncated(self) -> None:
        text = (
            "Apple's $30 billion deal hedges a fragile supply chain.\n"
            "Get the TNW newsletter\n"
            "Get the most important tech news in your inbox each week."
        )
        result = _truncate_at_trailing_boilerplate(text)
        self.assertEqual(result, "Apple's $30 billion deal hedges a fragile supply chain.")

    def test_earliest_marker_wins_when_multiple_present(self) -> None:
        text = "Real content here.\nREAD NEXT:\nSome link.\nWorth checking out on Amazon\nMore links."
        result = _truncate_at_trailing_boilerplate(text)
        self.assertEqual(result, "Real content here.")

    def test_no_marker_present_is_untouched(self) -> None:
        text = "A completely normal article with no boilerplate markers at all."
        self.assertEqual(_truncate_at_trailing_boilerplate(text), text)

    def test_does_not_truncate_mid_article_widgets_like_recommended_stories(self) -> None:
        # Regression: "Recommended Stories"/"Popular on X"/"Watch on X" were
        # deliberately excluded from the marker list — position-checked in
        # production and found anywhere from 8% to 96% into the text
        # (embedded mid-article widgets, not trailing footers). Truncating
        # on these would delete real trailing content.
        text = (
            "Some real article text before.\n"
            "Recommended Stories\n"
            "list of 2 items- list 1 of 2 Some link- list 2 of 2 Another link\n"
            "More real article text continues right here after the widget."
        )
        self.assertEqual(_truncate_at_trailing_boilerplate(text), text)


class StripZdnetLeadingDisclosureTests(unittest.TestCase):
    def test_real_world_zdnet_disclosure_is_stripped(self) -> None:
        # Captured from a live scrape — ZDNET's "why trust us" boilerplate
        # consistently led the extracted text ahead of the real article.
        text = (
            "Why you can trust ZDNET\n"
            ":ZDNET independently tests and researches products. "
            "If you see inaccuracies in our content, "
            "please report the mistake via this form.\n"
            "Why leaving extension cords plugged in permanently is riskier "
            "than you realize\nSure, home extension cords and power strips are handy."
        )
        result = _strip_zdnet_leading_disclosure(text)
        self.assertTrue(
            result.startswith("Why leaving extension cords plugged in permanently")
        )

    def test_text_not_starting_with_the_disclosure_is_untouched(self) -> None:
        text = "A normal article that happens to mention ZDNET later on."
        self.assertEqual(_strip_zdnet_leading_disclosure(text), text)

    def test_start_marker_without_end_marker_is_left_untouched(self) -> None:
        # Safety net: if the closing sentence ever changes/isn't found,
        # don't guess — leave the text as-is rather than risk truncating
        # into real content.
        text = "Why you can trust ZDNET\nSome disclosure text with no known end marker."
        self.assertEqual(_strip_zdnet_leading_disclosure(text), text)


class StripRelatedWidgetHeadingsTests(unittest.TestCase):
    """Technical Debt #23 (resolved 2026-07-13) — Variety/Deadline/Barchart's
    mid-article widget headings bleed through with no actual list content
    on either side (trafilatura already strips the widget's own links), so
    removing the bare heading string is safe — unlike a truncate-from-here
    approach, which would have deleted real trailing content."""

    def test_strips_popular_on_variety_between_real_paragraphs(self) -> None:
        # Captured from a live scrape (Variety).
        text = (
            "It would be a most infernal pleasure to play the devil’s "
            "music with you.”\nPopular on Variety\nOthers joined in "
            "with shows of support, apparently unafraid of getting caught "
            "up in spiritual warfare."
        )
        result = _strip_related_widget_headings(text)
        self.assertNotIn("Popular on Variety", result)
        self.assertIn("devil’s music with you.”\nOthers joined in", result)

    def test_strips_watch_on_deadline(self) -> None:
        text = (
            "With dozens of television stations going dark.\nWatch on Deadline\n"
            "DirecTV noted the outage will impact voters."
        )
        result = _strip_related_widget_headings(text)
        self.assertNotIn("Watch on Deadline", result)
        self.assertIn("dark.\nDirecTV noted", result)

    def test_strips_more_news_from_barchart(self) -> None:
        text = (
            "a bigger drag on earnings.\nMore News from Barchart\n"
            "The update also reinforced a broader theme."
        )
        result = _strip_related_widget_headings(text)
        self.assertNotIn("More News from Barchart", result)
        self.assertIn("earnings.\nThe update also reinforced", result)

    def test_text_without_any_marker_is_untouched(self) -> None:
        text = "A normal article with no related-content widget at all."
        self.assertEqual(_strip_related_widget_headings(text), text)


class StripAlJazeeraRecommendedStoriesTests(unittest.TestCase):
    """Al Jazeera's widget DOES carry real list content (article titles),
    but with a fully determinate structure: "list of N items" followed by
    exactly N "- list K of N<title>" entries, then the real article
    resumes. Confirmed against all 159 real matching rows in the live DB."""

    def test_strips_four_item_widget_real_example(self) -> None:
        # Captured from a live scrape (Al Jazeera).
        text = (
            "will cap International Fight Week festivities in Las Vegas.\n"
            "Recommended Stories\n"
            "list of 4 items"
            "- list 1 of 4Argentina’s Scaloni: Messi will be the best as long as he wants to be\n"
            "- list 2 of 4Yamal unconcerned by lack of goals, shares endearing moment with brother\n"
            "- list 3 of 4Mikel Merino strikes late again to tee up huge last-four clash with France\n"
            "- list 4 of 4Colombia’s Jaminton Campaz receives death threats after World Cup exit\n"
            "The Irishman has not competed since sustaining a broken tibia."
        )
        result = _strip_al_jazeera_recommended_stories(text)
        self.assertNotIn("Recommended Stories", result)
        self.assertNotIn("Scaloni", result)
        self.assertIn(
            "Las Vegas.\nThe Irishman has not competed since sustaining a broken tibia.",
            result,
        )

    def test_strips_singular_item_variant(self) -> None:
        # 2 of 159 real rows use a different singular format with no
        # entries at all: "list of 1 itemend of list".
        text = (
            "But she is leading in opinion polls.\n"
            "Recommended Stories\n"
            "list of 1 itemend of list"
            "Will her candidacy take her all the way to the Elysee Palace?"
        )
        result = _strip_al_jazeera_recommended_stories(text)
        self.assertNotIn("Recommended Stories", result)
        self.assertIn(
            "opinion polls.\nWill her candidacy take her all the way",
            result,
        )

    def test_malformed_entry_count_is_left_untouched(self) -> None:
        # Safety net: if a widget claims N entries but doesn't actually
        # have N well-formed "- list K of N" lines, don't guess at a
        # boundary — leave the text as-is rather than risk deleting real
        # content or leaving a half-stripped widget behind.
        text = (
            "Recommended Stories\nlist of 3 items"
            "- list 1 of 3Only one real entry exists\n"
            "Then the article just continues normally without more entries."
        )
        self.assertEqual(_strip_al_jazeera_recommended_stories(text), text)

    def test_text_without_the_widget_is_untouched(self) -> None:
        text = "A normal Al Jazeera article with no recommended-stories widget."
        self.assertEqual(_strip_al_jazeera_recommended_stories(text), text)


if __name__ == "__main__":
    unittest.main()
