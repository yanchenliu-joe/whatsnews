"""
Tests for narrative audio storage backend selection (2026-07-07) — Supabase
Storage was added so audio survives redeploys on hosts with an ephemeral
filesystem (e.g. Render's standard Web Service). No real HTTP/Supabase
calls are made; httpx.post is mocked throughout.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.narrative.audio_storage import (
    build_public_url,
    build_storage_path,
    delete_audio_file,
    save_audio_bytes,
)
from app.narrative import audio_service


class BuildPublicUrlTests(unittest.TestCase):
    def test_local_mode_returns_relative_media_path(self) -> None:
        with patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": "local"}):
            url = build_public_url("daily", "2026-07-01", 1, "female")
        self.assertEqual(url, "/media/audio/2026-07-01_daily_v1_female.mp3")

    def test_supabase_mode_returns_storage_public_url(self) -> None:
        with patch.dict(
            os.environ,
            {"VOICE_AUDIO_STORAGE": "supabase", "SUPABASE_URL": "https://abc.supabase.co"},
        ):
            url = build_public_url("daily", "2026-07-01", 1, "female")
        self.assertEqual(
            url,
            "https://abc.supabase.co/storage/v1/object/public/narrative-audio/"
            "2026-07-01_daily_v1_female.mp3",
        )


class GenerateNarrativeAudioStorageModeGuardTests(unittest.TestCase):
    """
    Regression test for a bug found live on Render (2026-07-07):
    generate_narrative_audio() had its own hardcoded storage-mode guard,
    separate from audio_storage.py's mode branching, that only accepted
    "local" and unconditionally failed every "supabase" mode run with
    "Unsupported VOICE_AUDIO_STORAGE: supabase. Use local for dev." —
    missed when Supabase Storage support was added because that work was
    verified via audio_storage.py's own functions and the one-off backfill
    script, never through this actual generate_narrative_audio() pipeline
    path.
    """

    def _mock_ready_narrative_row(self):
        return {
            "id": 1,
            "version": 1,
            "scope": "daily",
            "script_text": "This is a full narrative script with enough words to synthesize.",
        }

    def _run_with_storage_mode(self, storage_mode: str) -> dict:
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        with patch("app.narrative.audio_service.get_connection", return_value=mock_conn), \
             patch(
                 "app.narrative.audio_service.get_ready_narrative_row",
                 return_value=self._mock_ready_narrative_row(),
             ), \
             patch("app.narrative.audio_service.get_audio_variant_row", return_value=None), \
             patch("app.narrative.audio_service.upsert_audio_variant"), \
             patch("app.narrative.audio_service.update_narrative_audio"), \
             patch(
                 "app.narrative.audio_service.synthesize_speech",
                 return_value=(b"fake-mp3-bytes", "tts-1", "nova"),
             ), \
             patch("app.narrative.audio_service.save_audio_bytes"), \
             patch(
                 "app.narrative.audio_service.validate_audio_file",
                 return_value={"passed": True, "errors": [], "warnings": []},
             ), \
             patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": storage_mode}):
            return audio_service.generate_narrative_audio(voice_profile="female")

    def test_supabase_mode_passes_the_guard_and_succeeds(self) -> None:
        result = self._run_with_storage_mode("supabase")
        self.assertNotIn("Unsupported VOICE_AUDIO_STORAGE", str(result.get("error_message", "")))
        self.assertEqual(result.get("status"), "success")

    def test_local_mode_passes_the_guard_and_succeeds(self) -> None:
        result = self._run_with_storage_mode("local")
        self.assertNotIn("Unsupported VOICE_AUDIO_STORAGE", str(result.get("error_message", "")))
        self.assertEqual(result.get("status"), "success")

    def test_genuinely_unsupported_mode_still_fails_clearly(self) -> None:
        result = self._run_with_storage_mode("s3")
        self.assertEqual(result.get("status"), "failed")
        self.assertIn("Unsupported VOICE_AUDIO_STORAGE", result.get("error_message", ""))


class SaveAudioBytesTests(unittest.TestCase):
    def test_local_mode_writes_to_disk(self) -> None:
        with patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": "local"}):
            path = build_storage_path("daily", "2026-07-01", 1, "female")
            with patch("app.narrative.audio_storage.Path.mkdir") as mock_mkdir, \
                 patch("app.narrative.audio_storage.Path.write_bytes") as mock_write:
                save_audio_bytes(path, b"fake-mp3-bytes")
        mock_mkdir.assert_called_once()
        mock_write.assert_called_once_with(b"fake-mp3-bytes")

    def test_supabase_mode_uploads_via_http_instead_of_disk(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VOICE_AUDIO_STORAGE": "supabase",
                "SUPABASE_URL": "https://abc.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            },
        ):
            path = build_storage_path("daily", "2026-07-01", 1, "female")
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            with patch("httpx.post", return_value=mock_response) as mock_post, \
                 patch("app.narrative.audio_storage.Path.write_bytes") as mock_write:
                save_audio_bytes(path, b"fake-mp3-bytes")

        mock_write.assert_not_called()
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn(
            "https://abc.supabase.co/storage/v1/object/narrative-audio/"
            "2026-07-01_daily_v1_female.mp3",
            call_args.args[0],
        )
        self.assertEqual(call_args.kwargs["content"], b"fake-mp3-bytes")
        self.assertEqual(
            call_args.kwargs["headers"]["Authorization"], "Bearer test-service-role-key"
        )
        self.assertEqual(call_args.kwargs["headers"]["x-upsert"], "true")

    def test_supabase_mode_raises_when_credentials_missing(self) -> None:
        with patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": "supabase"}, clear=False):
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            path = build_storage_path("daily", "2026-07-01", 1, "female")
            with self.assertRaises(RuntimeError):
                save_audio_bytes(path, b"fake-mp3-bytes")


class DeleteAudioFileTests(unittest.TestCase):
    """
    Added alongside the archive retention job (app/retention/) — deleting a
    narrative's DB row was previously a no-op for the actual audio file on
    disk/Storage, which defeats the point of a retention job aimed at
    Supabase storage cost.
    """

    def test_local_mode_unlinks_the_file(self) -> None:
        with patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": "local"}):
            with patch("app.narrative.audio_storage.Path.unlink") as mock_unlink:
                result = delete_audio_file("daily", "2026-07-01", 1, "female")
        mock_unlink.assert_called_once_with(missing_ok=True)
        self.assertTrue(result)

    def test_local_mode_returns_false_on_os_error(self) -> None:
        with patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": "local"}):
            with patch(
                "app.narrative.audio_storage.Path.unlink", side_effect=OSError("boom")
            ):
                result = delete_audio_file("daily", "2026-07-01", 1, "female")
        self.assertFalse(result)

    def test_supabase_mode_deletes_via_http(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VOICE_AUDIO_STORAGE": "supabase",
                "SUPABASE_URL": "https://abc.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            },
        ):
            mock_response = MagicMock(status_code=200)
            with patch("httpx.delete", return_value=mock_response) as mock_delete:
                result = delete_audio_file("daily", "2026-07-01", 1, "female")

        self.assertTrue(result)
        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        self.assertIn(
            "https://abc.supabase.co/storage/v1/object/narrative-audio/"
            "2026-07-01_daily_v1_female.mp3",
            call_args.args[0],
        )
        self.assertEqual(
            call_args.kwargs["headers"]["Authorization"], "Bearer test-service-role-key"
        )

    def test_supabase_mode_treats_already_missing_as_success(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VOICE_AUDIO_STORAGE": "supabase",
                "SUPABASE_URL": "https://abc.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            },
        ):
            mock_response = MagicMock(status_code=404)
            with patch("httpx.delete", return_value=mock_response):
                result = delete_audio_file("daily", "2026-07-01", 1, "female")
        self.assertTrue(result)

    def test_supabase_mode_returns_false_when_credentials_missing(self) -> None:
        with patch.dict(os.environ, {"VOICE_AUDIO_STORAGE": "supabase"}, clear=False):
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            result = delete_audio_file("daily", "2026-07-01", 1, "female")
        self.assertFalse(result)

    def test_supabase_mode_returns_false_on_http_error(self) -> None:
        import httpx

        with patch.dict(
            os.environ,
            {
                "VOICE_AUDIO_STORAGE": "supabase",
                "SUPABASE_URL": "https://abc.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            },
        ):
            with patch("httpx.delete", side_effect=httpx.ConnectError("down")):
                result = delete_audio_file("daily", "2026-07-01", 1, "female")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
