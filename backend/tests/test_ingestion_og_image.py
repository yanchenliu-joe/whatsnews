"""
Tests for og:image fetching (app/ingestion/og_image.py).

_fetch_og_image() used to do a full (non-streaming) GET and only slice the
first 32KB *after* the entire page had already downloaded into memory —
og:image is always in <head>, so the rest of the page (often several MB of
scripts/images/tracking payloads) was fetched and held in memory just to be
thrown away. Found 2026-07-07 alongside the same issue in scrape.py while
tracking down OOM crashes on Render's Starter plan (512MB) during a full
20-topic pipeline run. Now streams and stops after _HEAD_READ_BYTES.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.ingestion.og_image import _fetch_og_image


def _mock_stream_response(status_code: int, chunks: list[bytes]):
    resp = MagicMock()
    resp.status_code = status_code
    resp.iter_bytes.return_value = iter(chunks)
    ctx = MagicMock()
    ctx.__enter__.return_value = resp
    ctx.__exit__.return_value = False
    return ctx


class FetchOgImageStreamingCapTests(unittest.TestCase):
    def test_finds_og_image_within_the_capped_head(self) -> None:
        html = (
            "<html><head>"
            '<meta property="og:image" content="https://example.com/pic.jpg">'
            "</head><body>" + ("x" * 100_000) + "</body></html>"
        )
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.stream.return_value = _mock_stream_response(200, [html.encode("utf-8")])

        with patch("httpx.Client", return_value=mock_client):
            result = _fetch_og_image("https://example.com/article")
        self.assertEqual(result, "https://example.com/pic.jpg")

    def test_non_200_status_returns_none(self) -> None:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.stream.return_value = _mock_stream_response(404, [b"not found"])

        with patch("httpx.Client", return_value=mock_client):
            self.assertIsNone(_fetch_og_image("https://example.com/missing"))

    def test_stops_after_head_cap_even_with_more_chunks_available(self) -> None:
        chunks = [b"<html><head>", b"x" * 50_000, b"y" * 50_000, b"z" * 50_000]
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        stream_ctx = _mock_stream_response(200, chunks)
        mock_client.stream.return_value = stream_ctx

        with patch("httpx.Client", return_value=mock_client), \
             patch("app.ingestion.og_image._HEAD_READ_BYTES", 60_000):
            _fetch_og_image("https://example.com/article")

        # iter_bytes was consumed but the function must not read past the cap
        # worth of chunks (3 of the 4 chunks cross the 60_000-byte cap).
        self.assertTrue(stream_ctx.__enter__.return_value.iter_bytes.called)


if __name__ == "__main__":
    unittest.main()
