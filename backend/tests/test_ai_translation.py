"""Tests for AIMode.TRANSLATION (Phase 32, added 2026-07-05).

Covers the new build_translation_prompt() (pure) and the gateway's mode
branch (dedicated prompt path + skips question-chip extraction). No test
makes a real OpenAI call — the provider and context builder are mocked.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai import prompt_builder
from app.ai.prompt_builder import build_translation_prompt
from app.ai.schemas import AIMode, ArticleContext, ChatRequest


class BuildTranslationPromptTests(unittest.TestCase):
    def test_uses_body_text_when_present(self) -> None:
        article = ArticleContext(title="Big news", body_text="Full article text here.", summary="A summary.")
        messages = build_translation_prompt(article, "Spanish")
        self.assertIn("Full article text here.", messages[1]["content"])
        self.assertNotIn("A summary.", messages[1]["content"])

    def test_falls_back_to_summary_when_no_body_text(self) -> None:
        article = ArticleContext(title="Big news", summary="A summary.")
        messages = build_translation_prompt(article, "Spanish")
        self.assertIn("A summary.", messages[1]["content"])

    def test_falls_back_to_why_it_matters_when_nothing_else(self) -> None:
        article = ArticleContext(title="Big news", why_it_matters="This matters because X.")
        messages = build_translation_prompt(article, "French")
        self.assertIn("This matters because X.", messages[1]["content"])

    def test_includes_target_language_and_title(self) -> None:
        article = ArticleContext(title="Big news", body_text="Text.")
        messages = build_translation_prompt(article, "Japanese")
        self.assertIn("Japanese", messages[1]["content"])
        self.assertIn("Big news", messages[1]["content"])

    def test_system_prompt_forbids_commentary(self) -> None:
        article = ArticleContext(title="X", body_text="Y")
        messages = build_translation_prompt(article, "German")
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Do not add commentary", messages[0]["content"])


class GatewayTranslationModeTests(unittest.IsolatedAsyncioTestCase):
    def _fake_context(self) -> MagicMock:
        context = MagicMock()
        context.metadata.related_articles_found = 0
        context.metadata.cross_topic_signals = 0
        context.metadata.build_time_ms = 1
        return context

    async def _collect(self, request: ChatRequest) -> list[str]:
        from app.ai.gateway import stream_chat_request
        lines = []
        async for line in stream_chat_request(request):
            lines.append(line)
        return lines

    async def test_translation_mode_uses_translation_prompt_not_insight(self) -> None:
        async def fake_stream(**kwargs):
            for chunk in ["Titulo traducido", "\n\nCuerpo traducido."]:
                yield chunk

        fake_provider = MagicMock()
        fake_provider.is_configured.return_value = True
        fake_provider.stream_chat = fake_stream

        request = ChatRequest(
            article=ArticleContext(title="Original title", body_text="Original body."),
            messages=[],
            mode=AIMode.TRANSLATION,
            language="Spanish",
        )

        with patch("app.ai.gateway.build_context_async", new=AsyncMock(return_value=self._fake_context())), \
             patch("app.ai.gateway._get_provider", return_value=fake_provider), \
             patch("app.ai.gateway.build_translation_prompt", wraps=prompt_builder.build_translation_prompt) as mock_translation_prompt, \
             patch("app.ai.gateway.build_insight_prompt") as mock_insight_prompt:
            lines = await self._collect(request)

        mock_translation_prompt.assert_called_once()
        mock_insight_prompt.assert_not_called()
        joined = "".join(lines)
        self.assertIn("Titulo traducido", joined)
        self.assertNotIn('"type": "questions"', joined)

    async def test_translation_mode_never_emits_questions_event_even_with_marker_text(self) -> None:
        async def fake_stream(**kwargs):
            yield "Translated text.\n---QUESTIONS---\n- Should not appear\n"

        fake_provider = MagicMock()
        fake_provider.is_configured.return_value = True
        fake_provider.stream_chat = fake_stream

        request = ChatRequest(
            article=ArticleContext(title="Original title", body_text="Original body."),
            messages=[],
            mode=AIMode.TRANSLATION,
            language="Chinese (Simplified)",
        )

        with patch("app.ai.gateway.build_context_async", new=AsyncMock(return_value=self._fake_context())), \
             patch("app.ai.gateway._get_provider", return_value=fake_provider):
            lines = await self._collect(request)

        joined = "".join(lines)
        self.assertNotIn('"type": "questions"', joined)


if __name__ == "__main__":
    unittest.main()
