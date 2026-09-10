"""Tests for the /ai/chat rate limiter (cost-abuse guard, added 2026-07-05).

/ai/chat is a public, unauthenticated endpoint that calls a paid OpenAI model
on every request. These tests lock in that it's now rate-limited per device
(or per client IP when no X-Device-Id header is sent), and that the limiter
itself behaves correctly in isolation. The real AI gateway is always mocked —
no test makes a network call to OpenAI.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.ai.rate_limit import check_rate_limit, clear_rate_limits

ARTICLE = {
    "title": "Test headline",
    "url": "https://example.com/a",
    "source": "Reuters",
    "topic": "Technology",
    "summary": "",
    "why_it_matters": "",
}


async def _fake_stream(_request):
    yield 'data: {"type": "delta", "text": "hi"}\n\n'
    yield "data: [DONE]\n\n"


class CheckRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rate_limits()

    def test_allows_requests_under_the_limit(self) -> None:
        for _ in range(5):
            allowed, retry_after = check_rate_limit("device:abc", max_requests=5, window_seconds=3600)
        # last call (5th) should still be allowed since limit is 5
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)

    def test_blocks_once_limit_is_reached(self) -> None:
        for _ in range(3):
            check_rate_limit("device:abc", max_requests=3, window_seconds=3600)
        allowed, retry_after = check_rate_limit("device:abc", max_requests=3, window_seconds=3600)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    def test_different_keys_have_independent_limits(self) -> None:
        for _ in range(3):
            check_rate_limit("device:abc", max_requests=3, window_seconds=3600)
        allowed, _ = check_rate_limit("device:xyz", max_requests=3, window_seconds=3600)
        self.assertTrue(allowed)

    def test_old_hits_outside_window_are_pruned(self) -> None:
        with patch("app.ai.rate_limit.time.monotonic", return_value=1000.0):
            for _ in range(3):
                check_rate_limit("device:abc", max_requests=3, window_seconds=60)
        # 61 seconds later, the window has fully rolled over.
        with patch("app.ai.rate_limit.time.monotonic", return_value=1061.0):
            allowed, retry_after = check_rate_limit("device:abc", max_requests=3, window_seconds=60)
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)

    def test_clear_rate_limits_resets_state(self) -> None:
        check_rate_limit("device:abc")
        cleared = clear_rate_limits()
        self.assertGreaterEqual(cleared, 1)
        self.assertEqual(clear_rate_limits(), 0)


class AiChatRouteRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.main as main
        from fastapi.testclient import TestClient
        clear_rate_limits()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        clear_rate_limits()

    def _post(self, device_id: str | None = None):
        headers = {"X-Device-Id": device_id} if device_id else {}
        return self.client.post(
            "/ai/chat",
            json={"article": ARTICLE, "messages": [], "mode": "article_insight"},
            headers=headers,
        )

    def test_requests_under_the_limit_succeed(self) -> None:
        with patch("app.ai.chat_routes.stream_chat_request", side_effect=_fake_stream), \
             patch("app.ai.chat_routes._MAX_REQUESTS_PER_WINDOW", 3):
            for _ in range(3):
                response = self._post(device_id="device-1")
                self.assertEqual(response.status_code, 200)

    def test_request_over_the_limit_returns_429_with_retry_after(self) -> None:
        with patch("app.ai.chat_routes.stream_chat_request", side_effect=_fake_stream), \
             patch("app.ai.chat_routes._MAX_REQUESTS_PER_WINDOW", 2):
            self._post(device_id="device-2")
            self._post(device_id="device-2")
            response = self._post(device_id="device-2")

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_different_devices_are_limited_independently(self) -> None:
        with patch("app.ai.chat_routes.stream_chat_request", side_effect=_fake_stream), \
             patch("app.ai.chat_routes._MAX_REQUESTS_PER_WINDOW", 1):
            self._post(device_id="device-a")
            response_a_second = self._post(device_id="device-a")
            response_b_first = self._post(device_id="device-b")

        self.assertEqual(response_a_second.status_code, 429)
        self.assertEqual(response_b_first.status_code, 200)

    def test_missing_device_id_falls_back_to_ip_based_limiting(self) -> None:
        with patch("app.ai.chat_routes.stream_chat_request", side_effect=_fake_stream), \
             patch("app.ai.chat_routes._MAX_REQUESTS_PER_WINDOW", 1):
            first = self._post()  # no X-Device-Id header
            second = self._post()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


if __name__ == "__main__":
    unittest.main()
