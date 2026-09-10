"""Optional OpenAI polish for narrative scripts."""

from __future__ import annotations

import os

from app.ai.registry import get_ai_provider
from app.narrative.generator import clean_for_speech, count_words, estimate_seconds
from app.narrative.models import NarrativeScript


def refine_narrative_with_ai(script: NarrativeScript) -> tuple[NarrativeScript, str, str | None]:
    """
    Polish script flow and transitions without adding new facts.

    Returns (script, ai_refine_status, model_name).
    """
    provider = get_ai_provider()
    if not provider.is_configured():
        return script, "no_key", None

    model = os.getenv("OPENAI_NARRATIVE_MODEL", "gpt-4o-mini")

    try:
        source_titles = [r.article_title for r in script.article_refs[:12]]
        prompt = (
            "You are editing a spoken morning intelligence briefing script for a news app.\n\n"
            "Rules:\n"
            "- Keep the same six sections in order: opening, top_story, key_developments, "
            "why_it_matters, what_to_watch_next, closing.\n"
            "- Improve spoken flow and transitions.\n"
            "- Do NOT add facts not present in the original.\n"
            "- Do NOT include URLs, bullet points, or markdown.\n"
            "- Keep at least the same length; do not shorten below 300 words.\n\n"
            f"Source article titles (ground truth): {source_titles}\n\n"
            f"Script to polish:\n{script.script_text}\n\n"
            "Return only the polished script with the same paragraph breaks (blank line between sections)."
        )

        result = provider.chat_completion(
            operation="narrative_refine",
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.2,
        )
        polished = result.text
        if not polished:
            return script, "ai_fallback", model

        paragraphs = [p.strip() for p in polished.split("\n\n") if p.strip()]
        if len(paragraphs) >= len(script.sections):
            for i, section in enumerate(script.sections):
                if i < len(paragraphs):
                    section.text = clean_for_speech(paragraphs[i])
                    section.estimated_seconds = estimate_seconds(count_words(section.text))

        script.script_text = "\n\n".join(s.text for s in script.sections)
        script.word_count = count_words(script.script_text)
        script.estimated_duration_seconds = estimate_seconds(script.word_count)
        script.ai_refine_status = "ai_success"
        script.model = model
        return script, "ai_success", model

    except Exception:
        script.ai_refine_status = "ai_fallback"
        return script, "ai_fallback", model
