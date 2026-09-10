"""Optional AI polish for editorial perspective (Phase 17.3)."""

from __future__ import annotations

import os

from app.perspective.models import EditorialPerspective


def refine_perspective_with_ai(
    perspective: EditorialPerspective,
    *,
    source_titles: list[str],
) -> tuple[EditorialPerspective, str, str | None]:
    """
    Polish headline and perspective prose without adding new facts.

    Returns (perspective, ai_status, model_name).
    """
    if os.getenv("ENABLE_PERSPECTIVE_AI_REFINE", "false").lower() != "true":
        return perspective, "disabled", None

    if not os.getenv("OPENAI_API_KEY"):
        return perspective, "no_key", None

    try:
        from app.ai.registry import get_ai_provider

        provider = get_ai_provider()
        model = os.getenv("OPENAI_PERSPECTIVE_MODEL", "gpt-4o-mini")
        evidence_lines = [
            f"- {item.get('topic')}: {item.get('title')}"
            for item in perspective.supporting_evidence[:5]
        ]
        prompt = (
            "You are writing an editorial perspective for a daily intelligence briefing.\n\n"
            "This is editorial judgment about what today's news means — not a summary.\n\n"
            f"Headline draft: {perspective.headline}\n"
            f"Perspective draft:\n{perspective.perspective}\n\n"
            f"Watch next bullets:\n" + "\n".join(f"- {w}" for w in perspective.watch_next) + "\n\n"
            f"Ground-truth article titles:\n" + "\n".join(evidence_lines) + "\n\n"
            "Rewrite headline (8–16 words) and perspective (120–220 words).\n"
            "Rules:\n"
            "- Do not invent facts beyond the drafts and titles.\n"
            "- Keep themes and watch-next intent.\n"
            "- Avoid: momentum, growing importance, implications, important, significant.\n\n"
            "Return JSON only:\n"
            '{"headline":"...","perspective":"..."}'
        )
        result = provider.chat_completion(
            operation="perspective_refine",
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        import json

        payload = json.loads(result.text.strip())
        headline = (payload.get("headline") or "").strip()
        text = (payload.get("perspective") or "").strip()
        if headline:
            perspective.headline = headline
        if text:
            perspective.perspective = text
        perspective.generation_method = "rule_v1+ai"
        perspective.model = model
        return perspective, "ai_success", model
    except Exception:
        return perspective, "ai_fallback", os.getenv("OPENAI_PERSPECTIVE_MODEL", "gpt-4o-mini")
