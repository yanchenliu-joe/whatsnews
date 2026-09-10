"""Audio generation configuration."""

from __future__ import annotations

import os
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

VOICE_PROFILE_FEMALE = "female"
VOICE_PROFILE_MALE = "male"

VOICE_PROFILES: frozenset[str] = frozenset({VOICE_PROFILE_FEMALE, VOICE_PROFILE_MALE})

PROFILE_LABELS: dict[str, str] = {
    VOICE_PROFILE_FEMALE: "Female",
    VOICE_PROFILE_MALE: "Male",
}


def audio_enabled_in_scheduler() -> bool:
    return os.getenv("ENABLE_VOICE_AUDIO_GENERATION", "false").lower() == "true"


def get_tts_provider() -> str:
    return os.getenv("VOICE_TTS_PROVIDER", "openai").lower().strip()


def get_tts_model() -> str:
    return os.getenv("VOICE_TTS_MODEL", "tts-1")


def get_tts_voice() -> str:
    return os.getenv("VOICE_TTS_VOICE", "nova")


OPENAI_TTS_VOICES: frozenset[str] = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
    }
)


def validate_tts_voice(voice: str) -> str:
    normalized = voice.lower().strip()
    if normalized not in OPENAI_TTS_VOICES:
        raise ValueError(
            f"Unsupported voice '{voice}'. "
            f"Choose one of: {', '.join(sorted(OPENAI_TTS_VOICES))}"
        )
    return normalized


def resolve_tts_voice(voice: str | None) -> str:
    if voice is None or not str(voice).strip():
        return validate_tts_voice(get_tts_voice())
    return validate_tts_voice(voice)


def get_default_voice_profile() -> str:
    raw = os.getenv("VOICE_DEFAULT_PROFILE", VOICE_PROFILE_FEMALE).lower().strip()
    return validate_voice_profile(raw)


def validate_voice_profile(profile: str) -> str:
    normalized = profile.lower().strip()
    if normalized not in VOICE_PROFILES:
        raise ValueError(
            f"Unsupported voice profile '{profile}'. "
            f"Choose one of: {', '.join(sorted(VOICE_PROFILES))}"
        )
    return normalized


def resolve_voice_profile(voice_profile: str | None) -> str:
    if voice_profile is None or not str(voice_profile).strip():
        return get_default_voice_profile()
    return validate_voice_profile(voice_profile)


def profile_label(profile: str) -> str:
    return PROFILE_LABELS.get(profile, profile)


def get_provider_voice_for_profile(profile: str) -> str:
    validated = validate_voice_profile(profile)
    if validated == VOICE_PROFILE_FEMALE:
        return validate_tts_voice(os.getenv("VOICE_PROFILE_FEMALE_VOICE", "nova"))
    return validate_tts_voice(os.getenv("VOICE_PROFILE_MALE_VOICE", "onyx"))


def provider_voice_to_profile(provider_voice: str | None) -> str | None:
    if not provider_voice:
        return None
    normalized = provider_voice.lower().strip()
    try:
        if normalized == get_provider_voice_for_profile(VOICE_PROFILE_FEMALE):
            return VOICE_PROFILE_FEMALE
        if normalized == get_provider_voice_for_profile(VOICE_PROFILE_MALE):
            return VOICE_PROFILE_MALE
    except ValueError:
        return None
    return None


def list_voice_profiles_payload() -> list[dict[str, str]]:
    return [
        {"id": VOICE_PROFILE_FEMALE, "label": PROFILE_LABELS[VOICE_PROFILE_FEMALE]},
        {"id": VOICE_PROFILE_MALE, "label": PROFILE_LABELS[VOICE_PROFILE_MALE]},
    ]


def get_audio_storage_mode() -> str:
    return os.getenv("VOICE_AUDIO_STORAGE", "local").lower().strip()


def get_local_audio_dir() -> Path:
    raw = os.getenv("VOICE_AUDIO_LOCAL_DIR", "media/audio")
    path = Path(raw)
    if not path.is_absolute():
        path = _BACKEND_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_audio_public_base_url() -> str:
    return os.getenv("VOICE_AUDIO_PUBLIC_BASE_URL", "http://127.0.0.1:8000/media/audio").rstrip("/")


def get_tts_max_chars() -> int:
    return int(os.getenv("VOICE_TTS_MAX_CHARS", "12000"))
