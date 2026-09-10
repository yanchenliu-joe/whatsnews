"""Tests for narrative audio generation concurrency (2026-07-06 speed pass).

Both synthesize_speech()'s per-chunk TTS calls and
generate_all_narrative_audio_variants()'s per-voice-profile calls now run
concurrently instead of sequentially, since every chunk/profile is an
independent output (distinct file path, distinct DB row) with no shared
mutable state. These tests confirm the parallelization is purely a speed
change — output order/content/semantics are unaffected. No real OpenAI or
DB calls are made.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from app.narrative import audio_service, audio_tts


class SynthesizeSpeechConcurrencyTests(unittest.TestCase):
    def _fake_provider(self, delays: dict[str, float]) -> MagicMock:
        provider = MagicMock()
        provider.is_configured.return_value = True

        def _text_to_speech(**kwargs):
            text = kwargs["text"]
            time.sleep(delays.get(text, 0))
            return text.encode("utf-8")

        provider.text_to_speech.side_effect = _text_to_speech
        return provider

    def test_chunk_order_preserved_even_when_first_chunk_finishes_last(self) -> None:
        chunks = ["chunk-A", "chunk-B", "chunk-C"]
        # First chunk deliberately slowest — if the join used completion
        # order instead of input order, the output would come out scrambled.
        provider = self._fake_provider({"chunk-A": 0.05, "chunk-B": 0.0, "chunk-C": 0.0})

        with patch("app.narrative.audio_tts.get_tts_provider", return_value="openai"), \
             patch("app.narrative.audio_tts.get_ai_provider", return_value=provider), \
             patch("app.narrative.audio_tts.split_tts_chunks", return_value=chunks):
            audio_bytes, model, voice = audio_tts.synthesize_speech("irrelevant full text")

        self.assertEqual(audio_bytes, b"chunk-Achunk-Bchunk-C")

    def test_count_as_generation_only_true_for_original_first_chunk(self) -> None:
        chunks = ["chunk-A", "chunk-B", "chunk-C"]
        provider = self._fake_provider({"chunk-A": 0.05})  # first chunk finishes last

        with patch("app.narrative.audio_tts.get_tts_provider", return_value="openai"), \
             patch("app.narrative.audio_tts.get_ai_provider", return_value=provider), \
             patch("app.narrative.audio_tts.split_tts_chunks", return_value=chunks):
            audio_tts.synthesize_speech("irrelevant full text")

        calls_by_text = {c.kwargs["text"]: c.kwargs["count_as_generation"] for c in provider.text_to_speech.call_args_list}
        self.assertEqual(calls_by_text, {"chunk-A": True, "chunk-B": False, "chunk-C": False})


class GenerateAllNarrativeAudioVariantsConcurrencyTests(unittest.TestCase):
    def test_both_profiles_generated_and_logged_when_run_concurrently(self) -> None:
        def _fake_generate(report_date, *, regenerate, voice_profile):
            # Male finishes first to prove result ordering doesn't depend on
            # completion order.
            time.sleep(0.05 if voice_profile == "female" else 0.0)
            return {"status": "ok", "report_date": "2026-07-06", "voice_profile": voice_profile}

        with patch("app.narrative.audio_service.narrative_ready_for_audio_generation", return_value=(True, None)), \
             patch("app.narrative.audio_service.generate_narrative_audio", side_effect=_fake_generate) as mock_gen, \
             patch("app.narrative.audio_service._profile_summary_from_result", side_effect=lambda r: {"status": r["status"]}), \
             patch("app.narrative.audio_service._aggregate_pipeline_audio_status", return_value="ok"):
            result = audio_service.generate_all_narrative_audio_variants(None, narrative_result={})

        self.assertEqual(mock_gen.call_count, 2)
        called_profiles = {c.kwargs["voice_profile"] for c in mock_gen.call_args_list}
        self.assertEqual(called_profiles, {"female", "male"})
        self.assertEqual(set(result["profiles"].keys()), {"female", "male"})
        self.assertEqual(result["profiles"]["female"]["status"], "ok")
        self.assertEqual(result["profiles"]["male"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
