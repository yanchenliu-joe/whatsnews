"""Post Processor — normalizes AI model output before delivery to clients.

All model output passes through here so formatting rules are enforced
in one place regardless of which provider produced the text.
"""

from __future__ import annotations

import re


def postprocess(text: str) -> str:
    """
    Normalize AI model output.

    Operations (order matters):
    1. Strip leading/trailing whitespace
    2. Collapse 3+ consecutive blank lines to 2
    3. Remove duplicate consecutive headings
    4. Normalize bullet point style (– → -)
    5. Trim trailing whitespace per line
    """
    if not text:
        return text

    text = text.strip()

    # Normalize en-dash / em-dash bullets to plain dash
    text = re.sub(r"^[–—]\s+", "- ", text, flags=re.MULTILINE)

    # Collapse 3+ blank lines to at most 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove duplicate consecutive headings (same ## heading appearing twice in a row)
    lines = text.splitlines()
    cleaned: list[str] = []
    prev_heading = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("#"):
            if stripped == prev_heading:
                continue
            prev_heading = stripped
        else:
            prev_heading = ""
        cleaned.append(stripped)

    return "\n".join(cleaned)


def extract_questions_section(text: str) -> tuple[str, list[str]]:
    """
    Splits the model output on the ---QUESTIONS--- marker.

    Returns:
        (insight_text, questions_list)

    If the marker is absent, returns (full text, []).
    """
    marker = "---QUESTIONS---"
    if marker not in text:
        return postprocess(text), []

    parts = text.split(marker, 1)
    insight_raw = parts[0].strip()
    questions_raw = parts[1].strip() if len(parts) > 1 else ""

    questions: list[str] = []
    for line in questions_raw.splitlines():
        q = line.strip().lstrip("- ").strip()
        if q and len(q) > 8:
            questions.append(q)
        if len(questions) >= 6:
            break

    return postprocess(insight_raw), questions
