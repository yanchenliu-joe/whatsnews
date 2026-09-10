"""Model Router — selects provider + model for a given request.

Phase 23: routing now considers AI_MODE, context richness, and complexity —
not just a flat task_type. The mode maps to a logical task tier; rich context
(many related articles / cross-topic signals) escalates to a stronger model.

Phase 23 still routes all providers to OpenAI. The routing rules and provider
registry are structured for future multi-provider support.

When a new provider is ready:
1. Add it to `_PROVIDERS` in ai/registry.py.
2. Add a per-task override in `_ROUTE_OVERRIDES` below (optional).
3. No other files need to change.
"""

from __future__ import annotations

from app.ai.config import get_ai_chat_config
from app.ai.schemas import AIMode, TaskType


class RoutingDecision:
    __slots__ = ("provider_name", "model_name", "task_type", "reason")

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        task_type: TaskType,
        reason: str = "",
    ) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.task_type = task_type
        self.reason = reason

    def __repr__(self) -> str:
        return (
            f"RoutingDecision(provider={self.provider_name!r}, "
            f"model={self.model_name!r}, task={self.task_type.value!r})"
        )


# AI_MODE → base TaskType tier
_MODE_TASK_MAP: dict[AIMode, TaskType] = {
    AIMode.ARTICLE_INSIGHT: TaskType.GENERAL,
    AIMode.SIMPLE_QA: TaskType.SUMMARIZE,
    AIMode.CROSS_TOPIC_ANALYSIS: TaskType.DEEP_ANALYSIS,
    AIMode.BRIEFING_ANALYSIS: TaskType.DEEP_ANALYSIS,
    AIMode.TREND_DETECTION: TaskType.DEEP_ANALYSIS,
    AIMode.MARKET_ANALYSIS: TaskType.INVESTMENT,
    AIMode.RESEARCH: TaskType.DEEP_ANALYSIS,
    AIMode.TRANSLATION: TaskType.TRANSLATION,
    # Backward-compat modes
    AIMode.DAILY_BRIEF: TaskType.GENERAL,
    AIMode.CROSS_TOPIC: TaskType.DEEP_ANALYSIS,
    AIMode.SOCIAL_MEDIA: TaskType.SUMMARIZE,
    AIMode.NEWSLETTER: TaskType.GENERAL,
}


class ModelRouter:
    """
    Selects which provider + model handles each request.

    Decision inputs (Phase 23):
      - mode             → base task tier (see _MODE_TASK_MAP)
      - context richness → escalation signal (related articles + cross-topic links)
      - complexity       → escalation signal (conversation depth)

    Escalation rule: a GENERAL/SUMMARIZE task with rich context (≥4 related
    articles OR ≥2 cross-topic signals) is promoted to DEEP_ANALYSIS so the
    model can actually reason over the larger context window.
    """

    # Optional per-task provider override. Empty = always use default_provider.
    # Example future entry: TaskType.TRANSLATION: "gemini"
    _ROUTE_OVERRIDES: dict[TaskType, str] = {}

    _RICH_RELATED_THRESHOLD = 4
    _RICH_CROSS_TOPIC_THRESHOLD = 2

    def select(
        self,
        *,
        mode: AIMode = AIMode.ARTICLE_INSIGHT,
        related_article_count: int = 0,
        cross_topic_count: int = 0,
        conversation_depth: int = 0,
    ) -> RoutingDecision:
        cfg = get_ai_chat_config()

        task_type = _MODE_TASK_MAP.get(mode, TaskType.GENERAL)
        reason = f"mode={mode.value}"

        # Context-richness escalation
        is_rich_context = (
            related_article_count >= self._RICH_RELATED_THRESHOLD
            or cross_topic_count >= self._RICH_CROSS_TOPIC_THRESHOLD
        )
        if task_type in (TaskType.GENERAL, TaskType.SUMMARIZE) and is_rich_context:
            task_type = TaskType.DEEP_ANALYSIS
            reason += f"; escalated:rich_context(rel={related_article_count},cross={cross_topic_count})"

        # Complexity escalation: long conversations need stronger coherence
        if task_type == TaskType.SUMMARIZE and conversation_depth >= 6:
            task_type = TaskType.GENERAL
            reason += f"; escalated:depth={conversation_depth}"

        provider = self._ROUTE_OVERRIDES.get(task_type, cfg.default_provider)

        model_map = {
            TaskType.SUMMARIZE: cfg.cheap_model,
            TaskType.DEEP_ANALYSIS: cfg.reasoning_model,
            TaskType.TRANSLATION: cfg.translation_model,
            TaskType.INVESTMENT: cfg.reasoning_model,
            TaskType.GENERAL: cfg.default_model,
        }
        model = model_map.get(task_type, cfg.default_model)

        return RoutingDecision(
            provider_name=provider,
            model_name=model,
            task_type=task_type,
            reason=reason,
        )


# Module-level singleton — callers import this directly.
model_router = ModelRouter()
