"""Quality checks for generated narrative audio."""

from __future__ import annotations

MIN_AUDIO_BYTES = 1024


def validate_audio_file(data: bytes, duration_seconds: int) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        errors.append("Audio file is empty.")
    elif len(data) < MIN_AUDIO_BYTES:
        errors.append("Audio file is too small to be valid.")

    if duration_seconds <= 0:
        errors.append("Audio duration must be greater than zero.")

    return {
        "passed": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }
