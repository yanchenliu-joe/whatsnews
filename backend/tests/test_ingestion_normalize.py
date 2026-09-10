"""Tests for RSS entry normalization, focused on truncation-artifact stripping."""

from __future__ import annotations

import unittest

from app.ingestion.normalize import (
    MIN_SUMMARY_LENGTH,
    _SUMMARY_MAX_LENGTH,
    _extract_body_text,
    _strip_body_boilerplate,
    _strip_truncation_artifacts,
    extract_summary_from_body,
    improve_summary_from_body,
    normalize_rss_entry,
    trim_trailing_partial_word,
    truncate_at_word_boundary,
)


class StripTruncationArtifactsTests(unittest.TestCase):
    def test_strips_bracket_ellipsis(self) -> None:
        self.assertEqual(
            _strip_truncation_artifacts("The story continues here [...]"),
            "The story continues here",
        )

    def test_strips_bracket_ellipsis_unicode_variant(self) -> None:
        self.assertEqual(
            _strip_truncation_artifacts("More details to follow […]"),
            "More details to follow",
        )

    def test_strips_wordpress_excerpt_footer(self) -> None:
        text = "Some teaser text here. The post Big News appeared first on Example Blog."
        self.assertEqual(_strip_truncation_artifacts(text), "Some teaser text here.")

    def test_strips_continue_reading_suffix(self) -> None:
        self.assertEqual(
            _strip_truncation_artifacts("Here is a preview of the story. Continue reading..."),
            "Here is a preview of the story.",
        )

    def test_strips_read_more_suffix(self) -> None:
        self.assertEqual(
            _strip_truncation_artifacts("Here is a preview. Read More"),
            "Here is a preview.",
        )

    def test_strips_trailing_ellipsis(self) -> None:
        self.assertEqual(
            _strip_truncation_artifacts("The situation is still developing..."),
            "The situation is still developing",
        )

    def test_leaves_clean_text_untouched(self) -> None:
        clean = "A fully formed sentence with no truncation markers."
        self.assertEqual(_strip_truncation_artifacts(clean), clean)

    def test_empty_and_none_safe(self) -> None:
        self.assertEqual(_strip_truncation_artifacts(""), "")
        self.assertEqual(_strip_truncation_artifacts(None), None)


class NormalizeRssEntrySummaryCleaningTests(unittest.TestCase):
    def test_summary_has_truncation_artifacts_stripped(self) -> None:
        entry = {
            "title": "Headline",
            "summary": "A short teaser about the story [...]",
            "link": "https://example.com/a",
        }
        result = normalize_rss_entry(entry, source="Example")
        self.assertEqual(result["summary"], "A short teaser about the story")

    def test_title_is_not_stripped_of_trailing_punctuation(self) -> None:
        entry = {
            "title": "Breaking News...",
            "summary": "",
            "link": "https://example.com/b",
        }
        result = normalize_rss_entry(entry, source="Example")
        # Titles deliberately bypass truncation stripping — only summary/body_text do.
        self.assertEqual(result["title"], "Breaking News...")


class ExtractBodyTextCleaningTests(unittest.TestCase):
    def test_body_text_has_truncation_artifacts_stripped(self) -> None:
        long_content = "x" * 150 + " and the rest of it [...]"
        entry = {"content": [{"value": long_content}]}
        result = _extract_body_text(entry)
        self.assertNotIn("[...]", result)
        self.assertTrue(result.endswith("and the rest of it"))

    def test_short_content_falls_back_to_empty(self) -> None:
        entry = {"content": [{"value": "too short [...]"}]}
        self.assertEqual(_extract_body_text(entry), "")


class TruncateAtWordBoundaryTests(unittest.TestCase):
    def test_leaves_short_text_untouched(self) -> None:
        self.assertEqual(truncate_at_word_boundary("short", 100), "short")

    def test_cuts_at_last_space_before_limit(self) -> None:
        text = "one two three four five"
        # Limit lands mid-word inside "three" — should back up to "two".
        result = truncate_at_word_boundary(text, 13)
        self.assertEqual(result, "one two…")
        self.assertFalse(result[:-1].endswith(" "))

    def test_never_severs_a_word(self) -> None:
        text = "responsibility. Understanding the situation fully"
        result = truncate_at_word_boundary(text, len("responsibility. Und"))
        self.assertNotIn("Und…", result)
        self.assertTrue(result.endswith("responsibility.…"))

    def test_appends_ellipsis_only_when_truncated(self) -> None:
        self.assertFalse(truncate_at_word_boundary("exact fit", 9).endswith("…"))


class TrimTrailingPartialWordTests(unittest.TestCase):
    def test_trims_dangling_word_and_appends_ellipsis(self) -> None:
        self.assertEqual(
            trim_trailing_partial_word("...that responsibility. Und"),
            "...that responsibility.…",
        )

    def test_empty_safe(self) -> None:
        self.assertEqual(trim_trailing_partial_word(""), "")

    def test_no_space_falls_back_to_appending_ellipsis(self) -> None:
        self.assertEqual(trim_trailing_partial_word("onelongword"), "onelongword…")


class ExtractSummaryFromBodyTests(unittest.TestCase):
    def test_short_body_returned_as_is(self) -> None:
        body = "One short sentence."
        self.assertEqual(extract_summary_from_body(body, min_length=450, max_length=650), body)

    def test_extends_to_first_sentence_boundary_past_min_length(self) -> None:
        # Each sentence is 20 chars incl. trailing space; min_length=45 should
        # land after the 3rd sentence (60 chars), not cut mid-sentence.
        sentence = "This is one part. "
        body = sentence * 10
        result = extract_summary_from_body(body, min_length=45, max_length=100)
        self.assertTrue(result.endswith("part."))
        self.assertGreaterEqual(len(result), 45)
        self.assertLessEqual(len(result), 100)

    def test_no_sentence_boundary_at_all_returns_empty(self) -> None:
        # Text with no sentence-ending punctuation anywhere in the window
        # (e.g. a navigation/menu dump) is refused rather than truncated
        # into a junk fragment — see extract_summary_from_body's docstring.
        body = "word " * 300  # 1500 chars, no sentence-ending punctuation at all
        result = extract_summary_from_body(body, min_length=450, max_length=650)
        self.assertEqual(result, "")

    def test_nav_dump_shorter_than_max_length_still_refused(self) -> None:
        # Real bug found 2026-07-13 (NASA feed): a nav/menu dump that
        # happens to be *shorter* than max_length used to pass straight
        # through via the "already short enough" branch, bypassing the
        # no-punctuation check entirely.
        nav_dump = (
            "Earth Observatory Earth Earth Observatory Image of the Day "
            "EO Explorer Topics All Topics Atmosphere Land Heat Radiation "
            "Life on Earth Human Dimensions Natural Events Oceans Remote "
            "Sensing Technology Snow Ice Water More"
        )
        self.assertLess(len(nav_dump), _SUMMARY_MAX_LENGTH)
        self.assertEqual(extract_summary_from_body(nav_dump), "")

    def test_long_lead_sentence_with_real_boundary_past_max_falls_back_to_word_boundary(
        self,
    ) -> None:
        # A genuinely long lead sentence (no boundary within the window)
        # but real prose overall (a boundary exists later) — different
        # from total nav-dump junk, so this still gets a usable, if
        # hard-truncated, summary rather than being refused outright.
        body = ("word " * 200) + ". " + ("more words " * 20)
        result = extract_summary_from_body(body, min_length=450, max_length=650)
        self.assertNotEqual(result, "")
        self.assertLessEqual(len(result), 651)

    def test_picks_first_boundary_at_or_past_min_length_not_last_under_max(self) -> None:
        # Sentence boundaries at 20, 40, 60, 80, 100 chars (approx). With
        # min_length=45, the boundary at ~60 should be picked, not the last
        # one before max_length=100.
        sentence = "Twenty chars here. "
        body = sentence * 6
        result = extract_summary_from_body(body, min_length=45, max_length=100)
        self.assertLess(len(result), 80)


class ImproveSummaryFromBodyTests(unittest.TestCase):
    def test_leaves_already_long_summary_untouched(self) -> None:
        long_summary = "x" * (MIN_SUMMARY_LENGTH + 50)
        body = "y" * 5000
        self.assertEqual(improve_summary_from_body(long_summary, body), long_summary)

    def test_leaves_summary_untouched_when_no_body_text(self) -> None:
        short = "Too short."
        self.assertEqual(improve_summary_from_body(short, ""), short)
        self.assertEqual(improve_summary_from_body(short, None), short)

    def test_leaves_summary_untouched_when_body_not_longer(self) -> None:
        short = "A summary that is short but body isn't longer than it."
        self.assertEqual(improve_summary_from_body(short, short[:10]), short)

    def test_replaces_short_summary_with_body_derived_one(self) -> None:
        short = "One sentence teaser."
        body = ("This is a much longer sentence with real content. " * 20).strip()
        result = improve_summary_from_body(short, body)
        self.assertGreater(len(result), len(short))
        self.assertTrue(body.startswith(result.rstrip("…").rstrip()))

    def test_empty_summary_gets_replaced(self) -> None:
        body = ("This is a much longer sentence with real content. " * 20).strip()
        result = improve_summary_from_body("", body)
        self.assertGreater(len(result), 0)

    def test_cleans_already_long_summary_even_without_extending(self) -> None:
        # A summary that's already >= MIN_SUMMARY_LENGTH still gets
        # boilerplate-stripped — found 2026-07-13: some RSS feeds embed
        # full article text (with site boilerplate) directly in their own
        # summary/description field, so "long enough" doesn't mean "clean".
        polluted = (
            "Real article content here that is long enough on its own. " * 4
            + "Click here to view full gallery at Hypebeast"
        )
        self.assertGreaterEqual(len(polluted), MIN_SUMMARY_LENGTH)
        result = improve_summary_from_body(polluted, "")
        self.assertNotIn("Click here", result)


class StripBodyBoilerplateTests(unittest.TestCase):
    def test_strips_copyright_footer(self) -> None:
        text = "Great article here. Copyright ©2026 Investor's Business Daily, LLC. All rights reserved. 87990cbe856818d5eddac44c7b1cdeb8"
        self.assertEqual(_strip_body_boilerplate(text), "Great article here.")

    def test_strips_hypebeast_gallery_cta(self) -> None:
        text = "The LEGO set is great. Click here to view full gallery at Hypebeast"
        self.assertEqual(_strip_body_boilerplate(text), "The LEGO set is great.")

    def test_strips_generic_click_here_cta(self) -> None:
        text = "Some intro. Click here for our daily hints and answers. More real content follows."
        result = _strip_body_boilerplate(text)
        self.assertNotIn("Click here", result)
        self.assertIn("More real content follows.", result)

    def test_strips_signup_cta(self) -> None:
        text = "Check out the game. Sign up here to get notified every time we publish a new GeoTemp! More text after."
        result = _strip_body_boilerplate(text)
        self.assertNotIn("Sign up", result)
        self.assertIn("More text after.", result)

    def test_strips_mit_newsletter_intro(self) -> None:
        text = (
            "This is today's edition of The Download, our weekday newsletter "
            "that provides a daily dose of what's going on in the world of "
            "technology. Anthropic found something."
        )
        self.assertEqual(_strip_body_boilerplate(text), "Anthropic found something.")

    def test_strips_cnet_puzzle_intro(self) -> None:
        text = (
            "Looking for the most recent Strands answer? Click here for our "
            "daily Strands hints, as well as our daily answers and hints for "
            "The New York Times Mini Crossword, Wordle, Connections and "
            "Connections: Sports Edition puzzles. Today was tough."
        )
        self.assertEqual(_strip_body_boilerplate(text), "Today was tough.")

    def test_strips_glued_leading_summary_label(self) -> None:
        text = "SummaryMarshall launches Acton IV and Stanmore IV with upgraded acoustics."
        self.assertEqual(
            _strip_body_boilerplate(text),
            "Marshall launches Acton IV and Stanmore IV with upgraded acoustics.",
        )

    def test_fixes_glued_sentences(self) -> None:
        text = "Marshall launches Acton IV.Features include wider soundstage.Iconic design updated."
        result = _strip_body_boilerplate(text)
        self.assertIn("Acton IV. Features", result)
        self.assertIn("soundstage. Iconic", result)

    def test_strips_indiewire_consent_disclaimer(self) -> None:
        text = (
            "By providing your information, you agree to our Terms of Use and "
            "our Privacy Policy. We use vendors that may also process your "
            "information to help provide our services. This site is protected "
            "by reCAPTCHA Enterprise and the Google Privacy Policy and Terms "
            "of Service apply. Over the course of his first three feature films, "
            "the director established himself as exciting."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("reCAPTCHA", result)
        self.assertTrue(result.startswith("Over the course of"))

    def test_strips_originally_appeared_newsletter_reprint(self) -> None:
        text = (
            "This post originally appeared in the BI Today newsletter. "
            "You can sign up for Business Insider's daily newsletter here. "
            "Should you invest in Trump Accounts?"
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertIn("Should you invest in Trump Accounts?", result)

    def test_strips_parenthetical_newsletter_intro(self) -> None:
        text = (
            "(This is the Warren Buffett Watch newsletter, news and analysis "
            "on all things Warren Buffett and Berkshire Hathaway. You can sign "
            "up here to receive it every Friday evening in your inbox.) "
            "With 2026 more than half over, Berkshire Hathaway's B shares are down."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertIn("Berkshire Hathaway's B shares are down.", result)

    def test_strips_subscribe_podcast_cta(self) -> None:
        text = (
            "Welcome to The Who What Wear Podcast. Subscribe to The Who What "
            "Wear Podcast on YouTube, Apple Podcasts, and Spotify. If you grew "
            "up obsessed with Legally Blonde, this episode is for you."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("Subscribe", result)
        self.assertIn("If you grew up obsessed with Legally Blonde", result)

    def test_strips_click_here_without_specific_followup_word(self) -> None:
        text = "Three wins to go. Click here to find out. Who: Norway vs England."
        result = _strip_body_boilerplate(text)
        self.assertNotIn("Click here", result)

    def test_strips_edition_of_newsletter_intro(self) -> None:
        text = (
            "This is an edition of the newsletter Box + Papers, Cam Wolf's "
            "weekly deep dive into the world of watches. Sign up here. We "
            "were waiting for our smash burgers to arrive."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertIn("We were waiting for our smash burgers", result)

    def test_strips_originally_published_on_and_subscribe_cta(self) -> None:
        text = (
            "This story was originally published on Grocery Dive. To receive "
            "daily news and insights, subscribe to our free daily Grocery Dive "
            "newsletter. At the end of last year, Albertsons launched an "
            "agentic shopping assistant."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertIn("Albertsons launched an agentic shopping assistant.", result)

    def test_strips_welcome_to_newsletter(self) -> None:
        text = (
            "Welcome to our institutional crypto newsletter. FalconX's Gaspar "
            "Martin writes that BTC is reaching a market bottom."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("Welcome", result)
        self.assertIn("FalconX's Gaspar Martin writes", result)

    def test_strips_published_by_signup_newsletters(self) -> None:
        text = (
            "This story was originally published by CalMatters. Sign up for "
            "their newsletters. California librarians were stunned when a "
            "last-minute budget change stripped K-12 schools of funding."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertTrue(result.startswith("California librarians"))

    def test_generic_newsletter_intro_heuristic_catches_unlisted_variants(self) -> None:
        # Structural fallback — deliberately not one of the specific
        # site patterns above, to prove the generic heuristic (first
        # sentence self-referentially mentions "newsletter") catches
        # variants we haven't individually seen yet.
        text = (
            "This is an edition of the newsletter Pulling Weeds, in which "
            "the columnist weighs in on hot topics. When I am down and out, "
            "scrolling endlessly, I think about pants."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertTrue(result.startswith("When I am down and out"))

    def test_generic_newsletter_intro_also_strips_immediate_signup_cta(self) -> None:
        text = (
            "A version of this story originally appeared in the BI Tech Memo "
            "newsletter. Sign up for the weekly BI Tech Memo newsletter here. "
            "Every week in the AI world brings new developments."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("newsletter", result.lower())
        self.assertTrue(result.startswith("Every week in the AI world"))

    def test_generic_newsletter_heuristic_leaves_third_party_news_alone(self) -> None:
        # A genuine news story that happens to be *about* a newsletter,
        # with no self-referential "this"/"our" framing, should NOT be
        # stripped by the generic heuristic.
        text = (
            "The New York Times launched a new newsletter for young "
            "readers this week. Executives said the goal is to build habits early."
        )
        result = _strip_body_boilerplate(text)
        self.assertIn("The New York Times launched", result)

    def test_read_more_marker_truncates_even_without_extraction(self) -> None:
        # Unlike the extract_summary_from_body hard-stop tests below, this
        # exercises _strip_body_boilerplate directly — covers an
        # already-long RSS summary that embeds "READ MORE:" and is never
        # run through the sentence-extraction path at all.
        text = (
            "The Cure have announced that Simon Gallup's son is filling in "
            "for him on tour. READ MORE: The Cure review a masterful "
            "reflection on loss Robert Smith and co. are out on tour."
        )
        result = _strip_body_boilerplate(text)
        self.assertNotIn("READ MORE", result)

    def test_strips_html_tags_and_entities_defensively(self) -> None:
        text = "<p>Monica Mendal is a writer, editor &amp; consultant.</p>"
        result = _strip_body_boilerplate(text)
        self.assertNotIn("<p>", result)
        self.assertIn("&", result)  # entity decoded, not stripped

    def test_leaves_clean_text_untouched(self) -> None:
        text = "A perfectly normal sentence. Another normal sentence follows."
        self.assertEqual(_strip_body_boilerplate(text), text)

    def test_preserves_single_newline_as_paragraph_break(self) -> None:
        # scrape.py's trafilatura call emits a single "\n" between
        # paragraphs/listicle items (confirmed against real stored
        # body_text, 2026-07-13) — found the same day: an earlier version
        # flattened every "\n" into a plain space, destroying formatting
        # ArticleDetailScreen.tsx's <Text> would otherwise render as real
        # line breaks (actively working against the "clear layout" goal).
        text = "First paragraph here.\nSecond paragraph here.\nThird paragraph here."
        result = _strip_body_boilerplate(text)
        self.assertEqual(
            result,
            "First paragraph here.\nSecond paragraph here.\nThird paragraph here.",
        )

    def test_collapses_multiple_consecutive_newlines_to_one(self) -> None:
        text = "First paragraph.\n\n\nSecond paragraph after extra blank lines."
        result = _strip_body_boilerplate(text)
        self.assertEqual(result, "First paragraph.\nSecond paragraph after extra blank lines.")

    def test_empty_safe(self) -> None:
        self.assertEqual(_strip_body_boilerplate(""), "")


class ExtractSummaryHardStopTests(unittest.TestCase):
    def test_stops_before_read_more_marker(self) -> None:
        text = (
            "The band played live at a recent show. READ MORE: Some other "
            "article title here about a completely different show that "
            "keeps going without punctuation The band then continued playing "
            "more songs for the audience for a very long time indeed."
        )
        result = extract_summary_from_body(text, min_length=10, max_length=300)
        self.assertNotIn("READ MORE", result)
        self.assertEqual(result, "The band played live at a recent show.")

    def test_strips_boilerplate_before_extracting(self) -> None:
        text = ("This is real article content. " * 30) + "Copyright ©2026 Some Publisher. All rights reserved."
        result = extract_summary_from_body(text, min_length=100, max_length=200)
        self.assertNotIn("Copyright", result)


if __name__ == "__main__":
    unittest.main()
