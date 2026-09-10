"""Tests for user preferences validation (Phase 38 adds ui_language)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.auth.preferences_repository import _validate_patch

VALID_USER_ID = "00000000-0000-0000-0000-000000000001"


class ValidatePatchUiLanguageTests(unittest.TestCase):
    def test_accepts_each_supported_language_code(self) -> None:
        for code in (
            "en", "zh-Hans", "zh-Hant", "es", "pt", "ja", "hi", "ar", "fr", "bn", "ru", "ur",
        ):
            validated = _validate_patch({"ui_language": code})
            self.assertEqual(validated, {"ui_language": code})

    def test_rejects_unsupported_language_code(self) -> None:
        with self.assertRaises(ValueError):
            _validate_patch({"ui_language": "de"})

    def test_rejects_non_string_value(self) -> None:
        with self.assertRaises(ValueError):
            _validate_patch({"ui_language": 123})


class PatchUserPreferencesUiLanguageTests(unittest.TestCase):
    def test_persists_ui_language(self) -> None:
        from app.auth.preferences_repository import patch_user_preferences

        cur = MagicMock()
        cur.fetchone.return_value = {"preferences": {"ui_language": "fr"}, "updated_at": None}
        conn = MagicMock()
        conn.cursor.return_value = cur

        with patch("app.auth.preferences_repository.get_connection", return_value=conn):
            result = patch_user_preferences(VALID_USER_ID, {"ui_language": "fr"})

        self.assertEqual(result["preferences"]["ui_language"], "fr")


if __name__ == "__main__":
    unittest.main()
