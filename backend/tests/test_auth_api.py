"""Auth API smoke tests (Phase 18.4.5)."""

from __future__ import annotations

import os
import unittest
from importlib import reload

import jwt
from fastapi.testclient import TestClient


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.auth.config as auth_config
        import app.main as main

        reload(auth_config)
        reload(main)

        # Pop after reload: database.py calls load_dotenv() during reload,
        # which restores values from .env (e.g. ENABLE_AUTH=true).
        # Clearing after reload ensures a clean disabled-auth baseline.
        os.environ.pop("ENABLE_AUTH", None)
        os.environ.pop("SUPABASE_JWT_SECRET", None)
        os.environ.pop("SUPABASE_URL", None)

        self.client = TestClient(main.app)

    def test_auth_disabled_endpoints_return_503(self) -> None:
        for path, method in [
            ("/auth/me", "get"),
            ("/me/saved-articles", "get"),
            ("/me/preferences", "get"),
        ]:
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.json()["detail"], "Auth disabled")

    def test_auth_enabled_without_token_returns_401(self) -> None:
        os.environ["ENABLE_AUTH"] = "true"

        import app.auth.config as auth_config

        reload(auth_config)

        for path, method in [
            ("/auth/me", "get"),
            ("/me/saved-articles", "get"),
            ("/me/preferences", "get"),
        ]:
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 401, response.text)

    def test_invalid_token_returns_401(self) -> None:
        os.environ["ENABLE_AUTH"] = "true"
        os.environ["SUPABASE_JWT_SECRET"] = "test-secret"

        import app.auth.config as auth_config
        import app.auth.jwt as auth_jwt

        reload(auth_config)
        reload(auth_jwt)

        headers = {"Authorization": "Bearer not.a.valid.jwt"}
        for path in ("/auth/me", "/me/saved-articles", "/me/preferences"):
            response = self.client.get(path, headers=headers)
            self.assertEqual(response.status_code, 401, response.text)
            self.assertEqual(response.json()["detail"], "Invalid or expired token.")

    def test_valid_token_decodes(self) -> None:
        os.environ["ENABLE_AUTH"] = "true"
        os.environ["SUPABASE_JWT_SECRET"] = "test-secret"
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"

        import app.auth.config as auth_config
        import app.auth.jwt as auth_jwt

        reload(auth_config)
        reload(auth_jwt)

        token = jwt.encode(
            {
                "sub": "00000000-0000-0000-0000-000000000001",
                "email": "user@example.com",
                "aud": "authenticated",
                "role": "authenticated",
                "exp": int(__import__("time").time()) + 3600,
                "iss": "https://example.supabase.co/auth/v1",
            },
            "test-secret",
            algorithm="HS256",
        )

        user = auth_jwt.decode_supabase_access_token(token)
        self.assertEqual(user.id, "00000000-0000-0000-0000-000000000001")
        self.assertEqual(user.email, "user@example.com")


if __name__ == "__main__":
    unittest.main()
