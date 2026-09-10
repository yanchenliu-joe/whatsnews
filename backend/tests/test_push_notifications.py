"""Tests for push notification deep-link data (added 2026-07-05).

Before this fix, push messages carried only title/body — tapping one just
opened the app to the default screen instead of the story it advertised.
`_build_push_copy()` now also returns a `data` dict ({"url", "topic"}) and
`_send_push_to_all_devices()` forwards it in the Expo message payload so the
mobile app can deep-link. No test hits the real Supabase instance or the real
Expo push API.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import app.main as main
from app.notifications.device_scheduler import _FALLBACK_PUSH_COPY, _build_push_copy
from app.notifications.push import _send_push_to_all_devices


def _fake_conn(fetchone_results=None, fetchall_results=None) -> MagicMock:
    fetchone_queue = list(fetchone_results or [])
    fetchall_queue = list(fetchall_results or [])
    cur = MagicMock()
    cur.fetchone.side_effect = lambda: fetchone_queue.pop(0) if fetchone_queue else None
    cur.fetchall.side_effect = lambda: fetchall_queue.pop(0) if fetchall_queue else []
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


class BuildPushCopyTests(unittest.TestCase):
    def test_no_report_falls_back_with_no_data(self) -> None:
        conn = _fake_conn(fetchone_results=[None])
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            title, body, data = _build_push_copy()
        self.assertEqual((title, body, data), _FALLBACK_PUSH_COPY)

    def test_top_article_produces_url_and_topic_in_data(self) -> None:
        conn = _fake_conn(
            fetchone_results=[{"topic_name": "Technology", "report_id": 1}],
            fetchall_results=[[
                {"title": "Big tech news", "summary": "Something happened.",
                 "why_it_matters": "This matters a lot.", "url": "https://example.com/a"},
            ]],
        )
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            title, body, data = _build_push_copy()

        self.assertEqual(title, "WhatsNews")
        self.assertIn("Big tech news", body)
        self.assertEqual(data, {"url": "https://example.com/a", "topic": "Technology"})

    def test_missing_article_url_produces_no_data(self) -> None:
        conn = _fake_conn(
            fetchone_results=[{"topic_name": "Technology", "report_id": 1}],
            fetchall_results=[[
                {"title": "Big tech news", "summary": "", "why_it_matters": "", "url": ""},
            ]],
        )
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            _, _, data = _build_push_copy()
        self.assertIsNone(data)

    def test_no_articles_falls_back_with_no_data(self) -> None:
        conn = _fake_conn(
            fetchone_results=[{"topic_name": "Technology", "report_id": 1}],
            fetchall_results=[[]],
        )
        with patch("app.notifications.device_scheduler.get_connection", return_value=conn):
            title, body, data = _build_push_copy()
        self.assertEqual((title, body, data), _FALLBACK_PUSH_COPY)


class SendPushToAllDevicesTests(unittest.TestCase):
    def test_data_is_included_in_each_expo_message(self) -> None:
        conn = _fake_conn(fetchall_results=[[{"push_token": "ExponentPushToken[abc]"}]])
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"data": [{"status": "ok"}]}

        with patch("app.notifications.push.get_connection", return_value=conn), \
             patch("app.notifications.push.httpx.post", return_value=fake_response) as mock_post:
            result = _send_push_to_all_devices(
                "WhatsNews", "Top story", {"url": "https://example.com/a", "topic": "Technology"}
            )

        sent_messages = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_messages[0]["data"], {"url": "https://example.com/a", "topic": "Technology"})
        self.assertEqual(result["status"], "ok")

    def test_none_data_becomes_empty_dict_in_payload(self) -> None:
        conn = _fake_conn(fetchall_results=[[{"push_token": "ExponentPushToken[abc]"}]])
        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"data": [{"status": "ok"}]}

        with patch("app.notifications.push.get_connection", return_value=conn), \
             patch("app.notifications.push.httpx.post", return_value=fake_response) as mock_post:
            _send_push_to_all_devices("WhatsNews", "Fallback copy", None)

        sent_messages = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_messages[0]["data"], {})


class AdminTestPushRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        from unittest.mock import patch as _patch
        from fastapi.testclient import TestClient
        self._env_patch = _patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("ADMIN_API_KEY", None)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self._env_patch.stop()

    def test_data_field_is_forwarded_to_send_push(self) -> None:
        with patch("app.admin.pipeline_routes._send_push_to_all_devices", return_value={"status": "ok", "sent": 1, "errors": 0}) as mock_send:
            response = self.client.post(
                "/admin/test-push",
                json={"title": "Test", "body": "Body", "data": {"url": "https://example.com/a", "topic": "Technology"}},
            )
        self.assertEqual(response.status_code, 200)
        mock_send.assert_called_once_with("Test", "Body", {"url": "https://example.com/a", "topic": "Technology"})

    def test_missing_data_field_passes_none(self) -> None:
        with patch("app.admin.pipeline_routes._send_push_to_all_devices", return_value={"status": "ok", "sent": 1, "errors": 0}) as mock_send:
            self.client.post("/admin/test-push", json={"title": "Test", "body": "Body"})
        mock_send.assert_called_once_with("Test", "Body", None)


if __name__ == "__main__":
    unittest.main()
