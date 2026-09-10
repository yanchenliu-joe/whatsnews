"""Shared Pydantic schemas for the AI Intelligence Platform (Phase 22)."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class AIMode(str, Enum):
    # ── Phase 23 intelligence modes ──────────────────────────────────────────
    ARTICLE_INSIGHT = "article_insight"            # Deep single-article explanation
    CROSS_TOPIC_ANALYSIS = "cross_topic_analysis"  # Compare/relate multiple topics
    BRIEFING_ANALYSIS = "briefing_analysis"        # Analyze the daily report
    TREND_DETECTION = "trend_detection"            # Detect patterns across time
    SIMPLE_QA = "simple_qa"                        # Direct question answering

    # ── Phase 22 modes (retained for backward compatibility) ─────────────────
    DAILY_BRIEF = "daily_brief"
    CROSS_TOPIC = "cross_topic"
    MARKET_ANALYSIS = "market_analysis"
    RESEARCH = "research"
    TRANSLATION = "translation"
    SOCIAL_MEDIA = "social_media"
    NEWSLETTER = "newsletter"


class TaskType(str, Enum):
    """Logical task categories used by the model router to select a model tier."""
    SUMMARIZE = "summarize"          # Cheap model — quick summaries
    DEEP_ANALYSIS = "deep_analysis"  # Strong reasoning model
    TRANSLATION = "translation"      # Fast multilingual model
    INVESTMENT = "investment"        # Highest reasoning model
    GENERAL = "general"              # Default model


class ArticleContext(BaseModel):
    title: str
    url: str = ""
    source: str = ""
    topic: str = ""
    summary: str = ""
    why_it_matters: str = ""
    body_text: str = ""  # Added 2026-07-05 (Phase 32) for full-article translation


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    article: ArticleContext
    messages: list[ChatMessage] = []
    mode: AIMode = AIMode.ARTICLE_INSIGHT
    date: Optional[str] = None   # YYYY-MM-DD, injected by frontend from current date
    # Response language for AIMode.TRANSLATION (e.g. "Spanish", "Chinese (Simplified)").
    # Wired into build_translation_prompt() as of 2026-07-05 — previously defined but
    # unused by any mode.
    language: str = "en"


# ─── SSE event shapes ─────────────────────────────────────────────────────────

class DeltaEvent(BaseModel):
    type: Literal["delta"] = "delta"
    text: str


class QuestionsEvent(BaseModel):
    type: Literal["questions"] = "questions"
    questions: list[str]


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


StreamEvent = DeltaEvent | QuestionsEvent | DoneEvent | ErrorEvent
