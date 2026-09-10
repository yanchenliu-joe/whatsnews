"""Tests for the Phase 29 entitlements module (RevenueCat webhook + /me/entitlement).

Covers the pure webhook-parsing logic, the DB-mocked repository, and the two
routes. No test hits the real Supabase instance or RevenueCat.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.auth.deps import get_current_user
from app.auth.models import AuthUser
from app.entitlements.repository import get_entitlement, is_premium, upsert_entitlement
from app.entitlements.webhook import UnparseableEvent, is_valid_user_id, parse_revenuecat_event

UTC = ZoneInfo("UTC")
NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)
VALID_USER_ID = "00000000-0000-0000-0000-000000000001"
ANON_USER_ID = "$RCAnonymousID:abc123"


def _payload(event: dict) -> dict:
    return {"api_version": "1.0", "event": event}


class ParseRevenueCatEventTests(unittest.TestCase):
    def test_missing_event_key_raises(self) -> None:
        with self.assertRaises(UnparseableEvent):
            parse_revenuecat_event({})

    def test_missing_app_user_id_raises(self) -> None:
        with self.assertRaises(UnparseableEvent):
            parse_revenuecat_event(_payload({"type": "INITIAL_PURCHASE"}))

    def test_initial_purchase_with_future_expiration_is_active(self) -> None:
        future_ms = int((datetime.now(tz=UTC) + timedelta(days=30)).timestamp() * 1000)
        result = parse_revenuecat_event(_payload({
            "type": "INITIAL_PURCHASE",
            "app_user_id": VALID_USER_ID,
            "entitlement_ids": ["premium"],
            "product_id": "annual_plan",
            "store": "APP_STORE",
            "expiration_at_ms": future_ms,
        }))
        self.assertTrue(result["is_active"])
        self.assertEqual(result["app_user_id"], VALID_USER_ID)
        self.assertEqual(result["entitlement_id"], "premium")
        self.assertEqual(result["product_id"], "annual_plan")
        self.assertEqual(result["store"], "APP_STORE")

    def test_expiration_event_is_never_active_even_with_future_timestamp(self) -> None:
        future_ms = int((NOW + timedelta(days=30)).timestamp() * 1000)
        result = parse_revenuecat_event(_payload({
            "type": "EXPIRATION",
            "app_user_id": VALID_USER_ID,
            "entitlement_ids": ["premium"],
            "expiration_at_ms": future_ms,
        }))
        self.assertFalse(result["is_active"])

    def test_past_expiration_is_not_active(self) -> None:
        past_ms = int((datetime.now(tz=UTC) - timedelta(days=1)).timestamp() * 1000)
        result = parse_revenuecat_event(_payload({
            "type": "RENEWAL",
            "app_user_id": VALID_USER_ID,
            "entitlement_ids": ["premium"],
            "expiration_at_ms": past_ms,
        }))
        self.assertFalse(result["is_active"])

    def test_no_expiration_and_non_deactivating_event_is_active(self) -> None:
        # Lifetime / non-consumable purchase — no expiration_at_ms at all.
        result = parse_revenuecat_event(_payload({
            "type": "NON_RENEWING_PURCHASE",
            "app_user_id": VALID_USER_ID,
            "entitlement_ids": ["premium"],
        }))
        self.assertTrue(result["is_active"])
        self.assertIsNone(result["expires_at"])

    def test_missing_entitlement_ids_defaults_to_premium(self) -> None:
        result = parse_revenuecat_event(_payload({
            "type": "INITIAL_PURCHASE",
            "app_user_id": VALID_USER_ID,
        }))
        self.assertEqual(result["entitlement_id"], "premium")


class IsValidUserIdTests(unittest.TestCase):
    def test_uuid_is_valid(self) -> None:
        self.assertTrue(is_valid_user_id(VALID_USER_ID))

    def test_revenuecat_anonymous_id_is_not_valid(self) -> None:
        self.assertFalse(is_valid_user_id(ANON_USER_ID))

    def test_empty_string_is_not_valid(self) -> None:
        self.assertFalse(is_valid_user_id(""))


def _fake_conn(fetchone_results=None) -> MagicMock:
    fetchone_queue = list(fetchone_results or [])
    cur = MagicMock()
    cur.fetchone.side_effect = lambda: fetchone_queue.pop(0) if fetchone_queue else None
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class RepositoryTests(unittest.TestCase):
    def test_upsert_entitlement_runs_insert_with_expected_params(self) -> None:
        conn = _fake_conn()
        cur = conn.cursor.return_value
        with patch("app.entitlements.repository.get_connection", return_value=conn):
            upsert_entitlement(
                VALID_USER_ID,
                is_active=True,
                product_id="annual_plan",
                store="APP_STORE",
                expires_at=NOW + timedelta(days=30),
                event_type="INITIAL_PURCHASE",
                raw_event={"event": {"type": "INITIAL_PURCHASE"}},
            )
        query, params = cur.execute.call_args[0]
        self.assertIn("ON CONFLICT (user_id, entitlement_id) DO UPDATE", query)
        self.assertEqual(params[0], VALID_USER_ID)
        self.assertEqual(params[1], "premium")
        self.assertTrue(params[2])
        conn.commit.assert_called_once()

    def test_get_entitlement_returns_none_when_missing(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.entitlements.repository.get_connection", return_value=conn):
            result = get_entitlement(VALID_USER_ID)
        self.assertIsNone(result)

    def test_get_entitlement_maps_row_to_dict(self) -> None:
        row = {
            "user_id": VALID_USER_ID, "entitlement_id": "premium", "is_active": True,
            "product_id": "annual_plan", "store": "APP_STORE",
            "expires_at": NOW + timedelta(days=30), "last_event_type": "INITIAL_PURCHASE",
            "updated_at": NOW,
        }
        conn = _fake_conn(fetchone_results=[row])
        with patch("app.entitlements.repository.get_connection", return_value=conn):
            result = get_entitlement(VALID_USER_ID)
        self.assertEqual(result["user_id"], VALID_USER_ID)
        self.assertTrue(result["is_active"])

    def test_is_premium_true_when_row_found(self) -> None:
        conn = _fake_conn(fetchone_results=[{"?column?": 1}])
        with patch("app.entitlements.repository.get_connection", return_value=conn):
            self.assertTrue(is_premium(VALID_USER_ID))

    def test_is_premium_false_when_no_row(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.entitlements.repository.get_connection", return_value=conn):
            self.assertFalse(is_premium(VALID_USER_ID))


class RevenueCatWebhookRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self.main = main
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_missing_secret_config_returns_503(self) -> None:
        os.environ.pop("REVENUECAT_WEBHOOK_SECRET", None)
        response = self.client.post("/webhooks/revenuecat", json=_payload({
            "type": "INITIAL_PURCHASE", "app_user_id": VALID_USER_ID,
        }))
        self.assertEqual(response.status_code, 503)

    def test_wrong_authorization_returns_401(self) -> None:
        os.environ["REVENUECAT_WEBHOOK_SECRET"] = "correct-secret"
        response = self.client.post(
            "/webhooks/revenuecat",
            json=_payload({"type": "INITIAL_PURCHASE", "app_user_id": VALID_USER_ID}),
            headers={"Authorization": "wrong-secret"},
        )
        self.assertEqual(response.status_code, 401)

    def test_valid_event_persists_and_returns_ok(self) -> None:
        os.environ["REVENUECAT_WEBHOOK_SECRET"] = "correct-secret"
        with patch("app.entitlements.routes.upsert_entitlement") as mock_upsert:
            response = self.client.post(
                "/webhooks/revenuecat",
                json=_payload({
                    "type": "INITIAL_PURCHASE",
                    "app_user_id": VALID_USER_ID,
                    "entitlement_ids": ["premium"],
                    "expiration_at_ms": int((NOW + timedelta(days=30)).timestamp() * 1000),
                }),
                headers={"Authorization": "correct-secret"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        mock_upsert.assert_called_once()
        self.assertEqual(mock_upsert.call_args[0][0], VALID_USER_ID)

    def test_anonymous_app_user_id_is_acknowledged_but_not_persisted(self) -> None:
        os.environ["REVENUECAT_WEBHOOK_SECRET"] = "correct-secret"
        with patch("app.entitlements.routes.upsert_entitlement") as mock_upsert:
            response = self.client.post(
                "/webhooks/revenuecat",
                json=_payload({"type": "INITIAL_PURCHASE", "app_user_id": ANON_USER_ID}),
                headers={"Authorization": "correct-secret"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ignored")
        mock_upsert.assert_not_called()

    def test_malformed_payload_is_acknowledged_not_persisted(self) -> None:
        os.environ["REVENUECAT_WEBHOOK_SECRET"] = "correct-secret"
        with patch("app.entitlements.routes.upsert_entitlement") as mock_upsert:
            response = self.client.post(
                "/webhooks/revenuecat",
                json={"api_version": "1.0"},  # no "event" key
                headers={"Authorization": "correct-secret"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ignored")
        mock_upsert.assert_not_called()

    def test_persist_error_is_swallowed_and_returns_200(self) -> None:
        os.environ["REVENUECAT_WEBHOOK_SECRET"] = "correct-secret"
        with patch("app.entitlements.routes.upsert_entitlement", side_effect=RuntimeError("fk violation")):
            response = self.client.post(
                "/webhooks/revenuecat",
                json=_payload({"type": "INITIAL_PURCHASE", "app_user_id": VALID_USER_ID}),
                headers={"Authorization": "correct-secret"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "error")


class MyEntitlementRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        self.main = main
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.main.app.dependency_overrides.pop(get_current_user, None)

    def test_returns_premium_status_for_authenticated_user(self) -> None:
        self.main.app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id=VALID_USER_ID, email="user@example.com"
        )
        with patch("app.entitlements.routes.is_premium", return_value=True), \
             patch("app.entitlements.routes.get_entitlement", return_value={"is_active": True}):
            response = self.client.get("/me/entitlement")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_premium"])

    def test_free_user_gets_false(self) -> None:
        self.main.app.dependency_overrides[get_current_user] = lambda: AuthUser(
            id=VALID_USER_ID, email="user@example.com"
        )
        with patch("app.entitlements.routes.is_premium", return_value=False), \
             patch("app.entitlements.routes.get_entitlement", return_value=None):
            response = self.client.get("/me/entitlement")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_premium"])


if __name__ == "__main__":
    unittest.main()
