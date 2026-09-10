"""AI Gateway — orchestrates the full intelligence request pipeline.

Route handlers call ONLY the gateway. The gateway is the only code that:
  - Talks to the prompt builder
  - Talks to the model router
  - Resolves a provider
  - Streams/fetches from the provider
  - Passes output through the post processor
  - Emits structured SSE events to callers

This ensures the route layer stays thin and providers are fully swappable.
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from app.ai.config import get_ai_chat_config
from app.ai.context_builder import build_context_async
from app.ai.postprocessor import extract_questions_section
from app.ai.prompt_builder import build_chat_prompt, build_insight_prompt, build_translation_prompt
from app.ai.registry import _PROVIDERS
from app.ai.router import model_router
from app.ai.schemas import (
    AIMode,
    ChatRequest,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    QuestionsEvent,
)


def _log(event: str, **kwargs) -> None:
    parts = [f"[whatsnews] event=ai_gateway.{event}"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v!r}")
    print(" ".join(parts), flush=True)


def _get_provider(provider_name: str):
    provider = _PROVIDERS.get(provider_name)
    if provider is None:
        raise ValueError(f"Unknown provider: {provider_name!r}")
    if not provider.is_configured():
        raise RuntimeError(
            f"Provider {provider_name!r} is not configured. "
            "Check the required API key environment variable."
        )
    return provider


async def stream_chat_request(request: ChatRequest) -> AsyncIterator[str]:
    """
    Full gateway pipeline — yields raw SSE lines ("data: {...}\\n\\n").

    Callers iterate and write directly to the HTTP response stream.
    SSE event shapes are defined in ai/schemas.py.

    Flow (Phase 23):
      1. Context Builder — build multi-source intelligence context
      2. Model Router — pick provider + model from mode + context richness
      3. Prompt Builder — format context into messages (no data fetching)
      4. Stream from provider
      5. Accumulate full text, then extract questions via post processor
      6. Emit delta events during streaming, then questions + done at the end
    """
    cfg = get_ai_chat_config()
    start_ms = int(time.monotonic() * 1000)

    try:
        # 1. CONTEXT BUILDER — construct the AI's "mental context"
        context = await build_context_async(
            article=request.article,
            mode=request.mode,
            date_str=request.date,
        )
        meta = context.metadata

        # 2. MODEL ROUTER — decide provider + model from mode + context richness
        decision = model_router.select(
            mode=request.mode,
            related_article_count=meta.related_articles_found,
            cross_topic_count=meta.cross_topic_signals,
            conversation_depth=len(request.messages),
        )
        provider = _get_provider(decision.provider_name)

        _log(
            "routed",
            mode=request.mode.value,
            provider=decision.provider_name,
            model=decision.model_name,
            task=decision.task_type.value,
            reason=decision.reason,
            context_related=meta.related_articles_found,
            context_cross_topic=meta.cross_topic_signals,
            context_build_ms=meta.build_time_ms,
        )

        # 3. PROMPT BUILDER — format context into messages (no fetching here)
        is_initial = len(request.messages) == 0

        if request.mode == AIMode.TRANSLATION:
            # Deliberately skips the multi-source context block (related
            # articles/cross-topic/global graph are noise for a translation
            # task) — see build_translation_prompt()'s docstring.
            messages = build_translation_prompt(
                article=request.article,
                target_language=request.language,
            )
        elif is_initial:
            messages = build_insight_prompt(
                context=context,
                mode=request.mode,
                date_str=request.date,
            )
        else:
            last_user = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                "",
            )
            history = [m for m in request.messages if not (m.role == "user" and m.content == last_user)]
            messages = build_chat_prompt(
                context=context,
                history=history,
                user_question=last_user,
                mode=request.mode,
                date_str=request.date,
            )

        # Stream from provider, accumulate full text for post-processing
        full_text_parts: list[str] = []

        async for chunk in provider.stream_chat(
            operation="ai_chat",
            model=decision.model_name,
            messages=messages,
            max_tokens=cfg.max_response_tokens,
            temperature=cfg.temperature,
        ):
            full_text_parts.append(chunk)
            event = DeltaEvent(text=chunk)
            yield f"data: {event.model_dump_json()}\n\n"

        full_text = "".join(full_text_parts)

        # Post-process and extract question chips from initial insight.
        # Translations never get follow-up question chips — not applicable.
        if is_initial and request.mode != AIMode.TRANSLATION:
            _, questions = extract_questions_section(full_text)
            if questions:
                q_event = QuestionsEvent(questions=questions)
                yield f"data: {q_event.model_dump_json()}\n\n"

        # Estimate token counts (provider already recorded actuals)
        from app.ai.pricing import estimate_tokens_from_text
        prompt_text = " ".join(m.get("content", "") for m in messages)
        input_tokens = estimate_tokens_from_text(prompt_text)
        output_tokens = max(1, len(full_text) // 4)
        elapsed_ms = int(time.monotonic() * 1000) - start_ms

        done_event = DoneEvent(
            model=decision.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed_ms,
        )
        yield f"data: {done_event.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as exc:
        error_event = ErrorEvent(message=str(exc)[:400])
        yield f"data: {error_event.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
