"""Public AI chat routes (Phase 22).

These routes are intentionally thin — they validate the request shape and
delegate everything to the AI Gateway. No business logic lives here.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.ai.gateway import stream_chat_request
from app.ai.rate_limit import check_rate_limit
from app.ai.schemas import ChatRequest

_MAX_REQUESTS_PER_WINDOW = 30
_WINDOW_SECONDS = 3600


def _rate_limit_key(http_request: Request, device_id: Optional[str]) -> str:
    if device_id:
        return f"device:{device_id}"
    client_ip = http_request.client.host if http_request.client else "unknown"
    return f"ip:{client_ip}"


def register_ai_chat_routes(app: FastAPI) -> None:

    @app.post("/ai/chat")
    async def ai_chat(
        request: ChatRequest,
        http_request: Request,
        x_device_id: Optional[str] = Header(default=None),
    ):
        """
        Streaming AI chat endpoint.

        Accepts structured article context + conversation history and streams
        a Server-Sent Events response.

        SSE event types:
          { "type": "delta", "text": "..." }          — partial token
          { "type": "questions", "questions": [...] }  — suggested follow-ups
          { "type": "done", "model": "...", ... }      — completion metadata
          { "type": "error", "message": "..." }        — recoverable error
          data: [DONE]                                 — stream sentinel

        Auth: public (no login required — this is not a login-gated feature).
        Rate limited per X-Device-Id header, falling back to client IP when
        the header is absent, at 30 requests/hour/key. This is a cost-abuse
        guard, not a premium/entitlement check — every real fetch here calls
        a paid OpenAI model.
        """
        key = _rate_limit_key(http_request, x_device_id)
        allowed, retry_after = check_rate_limit(
            key, max_requests=_MAX_REQUESTS_PER_WINDOW, window_seconds=_WINDOW_SECONDS
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many AI chat requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        return StreamingResponse(
            stream_chat_request(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
