"""Tests for the Phase 37 avatar module (PATCH /me/avatar).

Covers the DB-mocked repository function and the route. No test hits the
real Supabase instance or Storage — mobile uploads the image bytes
directly to Supabase Storage; this endpoint only ever persists the
resulting URL to profiles.avatar_url.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from app.auth.deps import get_current_user
from app.auth.models import AuthUser
from app.auth.repository import update_avatar_url

VALID_USER_ID = "00000000-0000-0000-0000-000000000001"
AVATAR_URL = "https://example.supabase.co/storage/v1/object/public/avatars/00000000-0000-0000-0000-000000000001/avatar.jpg"


def _fake_conn(fetchone_result=None) -> MagicMock:
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_result
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class UpdateAvatarUrlRepositoryTests(unittest.TestCase):
    def test_updates_and_returns_profile(self) -> None:
        row = {
            "id": VALID_USER_ID,
            "email": "user@example.com",
            "display_name": "User",
            "avatar_url": AVATAR_URL,
            "created_at": None,
        }
        conn = _fake_conn(fetchone_result=row)
        with patch("app.auth.repository.get_connection", return_value=conn):
            profile = update_avatar_url(VALID_USER_ID, AVATAR_URL)

        self.assertEqual(profile.avatar_url, AVATAR_URL)
        cur = conn.cursor.return_value
        params = cur.execute.call_args[0][1]
        self.assertEqual(params, (AVATAR_URL, VALID_USER_ID))
        conn.commit.assert_called_once()

    def test_missing_profile_raises_value_error(self) -> None:
        conn = _fake_conn(fetchone_result=None)
        with patch("app.auth.repository.get_connection", return_value=conn):
            with self.assertRaises(ValueError):
                update_avatar_url(VALID_USER_ID, AVATAR_URL)

    def test_db_error_rolls_back_and_raises_runtime_error(self) -> None:
        import psycopg2

        conn = _fake_conn()
        conn.cursor.return_value.execute.side_effect = psycopg2.Error("boom")
        with patch("app.auth.repository.get_connection", return_value=conn):
            with self.assertRaises(RuntimeError):
                update_avatar_url(VALID_USER_ID, AVATAR_URL)
        conn.rollback.assert_called_once()


class PatchMyAvatarRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient

        self.main = main
        self.client = TestClient(main.app)
        # Other test modules mutate ENABLE_AUTH process-wide and don't always
        # reset it; force a clean disabled-by-default baseline regardless of
        # discovery order, matching test_auth_api.py's own defensive setUp.
        self._enable_auth_patch = patch.dict(os.environ, {}, clear=False)
        self._enable_auth_patch.start()
        os.environ.pop("ENABLE_AUTH", None)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.pop(get_current_user, None)
        self._enable_auth_patch.stop()

    def test_auth_disabled_returns_503_without_override(self) -> None:
        # No dependency override and ENABLE_AUTH unset in this process ->
        # require_auth_enabled() raises 503 before token parsing, matching
        # every other auth-gated endpoint's disabled-by-default behavior.
        response = self.client.patch("/me/avatar", json={"avatar_url": AVATAR_URL})
        self.assertEqual(response.status_code, 503)

    def test_signed_in_user_updates_avatar(self) -> None:
        self.main.app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id=VALID_USER_ID, email="user@example.com"
        )
        with patch("app.auth.avatar_routes.update_avatar_url") as mock_update:
            mock_update.return_value = MagicMock(
                id=VALID_USER_ID,
                email="user@example.com",
                display_name="User",
                avatar_url=AVATAR_URL,
            )
            response = self.client.patch("/me/avatar", json={"avatar_url": AVATAR_URL})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["avatar_url"], AVATAR_URL)
        mock_update.assert_called_once_with(VALID_USER_ID, AVATAR_URL)

    def test_empty_avatar_url_rejected(self) -> None:
        self.main.app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id=VALID_USER_ID, email="user@example.com"
        )
        with patch("app.auth.avatar_routes.update_avatar_url") as mock_update:
            response = self.client.patch("/me/avatar", json={"avatar_url": "   "})

        self.assertEqual(response.status_code, 400)
        mock_update.assert_not_called()

    def test_missing_avatar_url_field_rejected(self) -> None:
        self.main.app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id=VALID_USER_ID, email="user@example.com"
        )
        response = self.client.patch("/me/avatar", json={})
        self.assertEqual(response.status_code, 422)

    def test_profile_not_found_returns_400(self) -> None:
        self.main.app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id=VALID_USER_ID, email="user@example.com"
        )
        with patch(
            "app.auth.avatar_routes.update_avatar_url",
            side_effect=ValueError("Profile not found."),
        ):
            response = self.client.patch("/me/avatar", json={"avatar_url": AVATAR_URL})

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
