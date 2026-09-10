"""Prepare narrative script text for TTS."""

from __future__ import annotations

import re

from app.narrative.generator import clean_for_speech, count_words
from app.narrative.audio_config import get_tts_max_chars

MARKDOWN_PATTERN = re.compile(r"[*_#>`\[\]]+")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

OPENAI_TTS_CHUNK_CHARS = 4096


def prepare_script_for_tts(script_text: str) -> str:
    """Normalize script_text for speech synthesis."""
    text = script_text or ""
    text = MARKDOWN_PATTERN.sub("", text)
    text = URL_PATTERN.sub("", text)
    text = clean_for_speech(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    max_chars = get_tts_max_chars()
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."

    return text


def split_tts_chunks(text: str, max_chars: int = OPENAI_TTS_CHUNK_CHARS) -> list[str]:
    """Split text into chunks under OpenAI per-request limits."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(para) <= max_chars:
            current = para
        else:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            buf = ""
            for sentence in sentences:
                piece = f"{buf} {sentence}".strip() if buf else sentence
                if len(piece) <= max_chars:
                    buf = piece
                else:
                    if buf:
                        chunks.append(buf)
                    buf = sentence[:max_chars]
            if buf:
                current = buf

    if current:
        chunks.append(current)

    flat = [c for c in chunks if c.strip()]
    if not flat:
        return _hard_split(text, max_chars)

    merged: list[str] = []
    for chunk in flat:
        if len(chunk) <= max_chars:
            merged.append(chunk)
        else:
            merged.extend(_hard_split(chunk, max_chars))

    return merged


def _hard_split(text: str, max_chars: int) -> list[str]:
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def estimate_duration_from_words(text: str) -> int:
    return max(1, int((count_words(text) / 150) * 60))
