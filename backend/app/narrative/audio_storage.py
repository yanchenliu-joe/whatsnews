"""
Local and Supabase Storage helpers for narrative audio files.

Storage backend is chosen by VOICE_AUDIO_STORAGE ("local", the default, or
"supabase"). Supabase Storage was added 2026-07-07 to survive redeploys on
hosts with an ephemeral filesystem (e.g. Render's standard Web Service) —
local disk audio would otherwise be wiped on every redeploy, permanently
breaking Archive/History voice playback for every past date with no
auto-recovery, since the DB only stores a URL/path string and never
verifies the file still exists.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from app.auth.config import supabase_url
from app.narrative.audio_config import get_audio_storage_mode, get_local_audio_dir

_SUPABASE_BUCKET = "narrative-audio"
_UPLOAD_TIMEOUT_SECONDS = 30


def _build_filename(
    scope: str,
    report_date: str,
    version: int,
    voice_profile: str,
) -> str:
    return f"{report_date}_{scope}_v{version}_{voice_profile}.mp3"


def build_storage_path(
    scope: str,
    report_date: str,
    version: int,
    voice_profile: str,
) -> Path:
    """
    Local filesystem path for this audio variant. Still returned in
    "supabase" mode too (used only for logging and as the DB
    audio_storage_path value, which is never read back as a real
    filesystem path — see _variant_ready_for_version()'s substring check
    in audio_service.py) — no local file is actually written in that mode.
    """
    filename = _build_filename(scope, report_date, version, voice_profile)
    return get_local_audio_dir() / filename


def build_public_url(
    scope: str,
    report_date: str,
    version: int,
    voice_profile: str,
) -> str:
    """Public URL clients fetch the audio from."""
    filename = _build_filename(scope, report_date, version, voice_profile)
    if get_audio_storage_mode() == "supabase":
        base = (supabase_url() or "").rstrip("/")
        return f"{base}/storage/v1/object/public/{_SUPABASE_BUCKET}/{filename}"
    return f"/media/audio/{filename}"


def _upload_to_supabase_storage(filename: str, data: bytes) -> None:
    base = (supabase_url() or "").rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required when "
            "VOICE_AUDIO_STORAGE=supabase"
        )
    resp = httpx.post(
        f"{base}/storage/v1/object/{_SUPABASE_BUCKET}/{filename}",
        headers={
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key,
            "Content-Type": "audio/mpeg",
            "x-upsert": "true",
        },
        content=data,
        timeout=_UPLOAD_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()


def save_audio_bytes(path: Path, data: bytes) -> None:
    if get_audio_storage_mode() == "supabase":
        _upload_to_supabase_storage(path.name, data)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _delete_from_supabase_storage(filename: str) -> bool:
    base = (supabase_url() or "").rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not service_role_key:
        return False
    try:
        resp = httpx.delete(
            f"{base}/storage/v1/object/{_SUPABASE_BUCKET}/{filename}",
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
            },
            timeout=_UPLOAD_TIMEOUT_SECONDS,
        )
        # 200 = deleted, 404 = already gone — both are a successful end state.
        return resp.status_code in (200, 404)
    except httpx.HTTPError:
        return False


def delete_audio_file(
    scope: str,
    report_date: str,
    version: int,
    voice_profile: str,
) -> bool:
    """
    Delete one audio file, local disk or Supabase Storage depending on
    VOICE_AUDIO_STORAGE. Used by the archive retention job (app/retention/) —
    deleting the DB row alone does not free storage space, since neither
    backend had any deletion path before this. Missing files are treated as
    success (nothing left to clean up).
    """
    filename = _build_filename(scope, report_date, version, voice_profile)
    if get_audio_storage_mode() == "supabase":
        return _delete_from_supabase_storage(filename)
    path = get_local_audio_dir() / filename
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def estimate_mp3_duration_seconds(data: bytes, fallback_seconds: int) -> int:
    """Rough duration from byte size; falls back to word-based estimate."""
    if not data:
        return 0
    # Typical OpenAI tts-1 MP3 ~128kbps effective for speech.
    estimated = int((len(data) * 8) / (128 * 1000))
    if estimated <= 0:
        return fallback_seconds
    return max(estimated, fallback_seconds)
