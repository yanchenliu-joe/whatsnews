"""Quality gate for narrative scripts."""

from __future__ import annotations

import re

from app.narrative.models import CANONICAL_SECTION_IDS, NarrativeScript

MIN_WORDS = 500
MAX_WORDS = 1800
MIN_ARTICLE_REFS = 3
URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)


def run_quality_gate(script: NarrativeScript) -> dict:
    warnings: list[str] = []
    errors: list[str] = []

    section_ids = [s.id for s in script.sections]
    if section_ids != list(CANONICAL_SECTION_IDS):
        errors.append(f"Invalid section order or ids: {section_ids}")

    for section in script.sections:
        if not (section.text or "").strip():
            errors.append(f"Section '{section.id}' is empty.")
        if URL_PATTERN.search(section.text):
            errors.append(f"Section '{section.id}' contains URL-like text.")

    if script.word_count < 300:
        errors.append(f"Word count {script.word_count} too low (minimum 300).")
    elif script.word_count < MIN_WORDS:
        warnings.append(f"Word count {script.word_count} below target ({MIN_WORDS}).")
    if script.word_count > MAX_WORDS:
        warnings.append(f"Word count {script.word_count} above target ({MAX_WORDS}).")

    unique_refs = len({(r.topic_id, r.article_title, r.report_id) for r in script.article_refs})
    if unique_refs < MIN_ARTICLE_REFS:
        errors.append(f"Too few article refs ({unique_refs}); need at least {MIN_ARTICLE_REFS}.")

    if not script.source_report_ids:
        errors.append("Missing source_report_ids.")

    passed = len(errors) == 0
    return {
        "passed": passed,
        "warnings": warnings,
        "errors": errors,
    }
