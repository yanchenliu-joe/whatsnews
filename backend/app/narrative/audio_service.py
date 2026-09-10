"""Orchestrate narrative TTS audio generation and persistence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.database import get_connection
from app.briefing_repository import get_latest_daily_report_date
from app.narrative.audio_config import (
    VOICE_PROFILE_FEMALE,
    VOICE_PROFILE_MALE,
    get_audio_storage_mode,
    get_default_voice_profile,
    get_provider_voice_for_profile,
    provider_voice_to_profile,
    resolve_tts_voice,
    resolve_voice_profile,
)
from app.narrative.audio_prepare import estimate_duration_from_words, prepare_script_for_tts
from app.narrative.audio_quality import validate_audio_file
from app.narrative.audio_storage import (
    build_public_url,
    build_storage_path,
    estimate_mp3_duration_seconds,
    save_audio_bytes,
)
from app.narrative.audio_tts import TTSConfigurationError, TTSGenerationError, synthesize_speech
from app.narrative.repository import (
    get_audio_variant_row,
    get_ready_narrative_row,
    update_narrative_audio,
    upsert_audio_variant,
)


def _log(event: str, **kwargs) -> None:
    context = " ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    print(f"[whatsnews] event={event} {context}".strip())


def _pipeline(stage: str, report_date: str, **kwargs) -> None:
    _log("voice_pipeline", stage=stage, report_date=report_date, **kwargs)


def _pipeline_failed(stage: str, report_date: str, **kwargs) -> None:
    _log("voice_pipeline_failed", stage=stage, report_date=report_date, **kwargs)


def _resolve_generation_targets(
    voice_profile: str | None,
    voice: str | None,
) -> tuple[str, str]:
    if voice_profile is not None and str(voice_profile).strip():
        profile = resolve_voice_profile(voice_profile)
        return profile, get_provider_voice_for_profile(profile)

    if voice is not None and str(voice).strip():
        provider_voice = resolve_tts_voice(voice)
        profile = provider_voice_to_profile(provider_voice) or get_default_voice_profile()
        return profile, provider_voice

    profile = resolve_voice_profile(None)
    return profile, get_provider_voice_for_profile(profile)


def _mark_variant_failed(
    cur,
    narrative_id: int,
    voice_profile: str,
    message: str,
) -> None:
    upsert_audio_variant(
        cur,
        narrative_id,
        voice_profile,
        audio_status="failed",
        audio_error_message=message,
    )
    if voice_profile == get_default_voice_profile():
        update_narrative_audio(
            cur,
            narrative_id,
            audio_status="failed",
            audio_error_message=message,
        )


_PIPELINE_VOICE_PROFILES = (VOICE_PROFILE_FEMALE, VOICE_PROFILE_MALE)


def _variant_ready_for_version(
    variant_row: dict,
    *,
    scope: str,
    date_str: str,
    version: int,
    voice_profile: str,
) -> bool:
    if variant_row.get("audio_status") != "ready" or not variant_row.get("audio_url"):
        return False
    expected_suffix = f"_v{version}_{voice_profile}.mp3"
    url = str(variant_row.get("audio_url") or "")
    storage = str(variant_row.get("audio_storage_path") or "")
    return expected_suffix in url or expected_suffix in storage


def narrative_ready_for_audio_generation(narrative_result: dict | None) -> tuple[bool, str | None]:
    """True when the pipeline narrative stage produced or found a ready script."""
    if not narrative_result or "error" in narrative_result:
        return False, "narrative_stage_error"
    status = narrative_result.get("status")
    if status == "failed":
        return False, "narrative_generation_failed"
    if status == "error":
        return False, "narrative_stage_error"
    if status == "skipped":
        if narrative_result.get("reason") == "ready_exists":
            return True, None
        return False, narrative_result.get("reason") or "narrative_not_ready"
    if status == "success":
        return True, None
    return False, "narrative_not_ready"


def _profile_summary_from_result(result: dict) -> dict:
    status = result.get("status")
    if status == "success":
        return {
            "status": "ready",
            "audio_url": result.get("audio_url"),
            "duration_seconds": result.get("audio_duration_seconds"),
        }
    if status == "skipped" and result.get("reason") == "ready_audio_exists":
        return {
            "status": "ready",
            "audio_url": result.get("audio_url"),
            "duration_seconds": result.get("audio_duration_seconds"),
        }
    if status == "skipped":
        return {
            "status": "skipped",
            "error_message": result.get("reason"),
        }
    if status == "failed":
        return {
            "status": "failed",
            "error_message": result.get("error_message") or result.get("detail"),
        }
    return {
        "status": "failed",
        "error_message": result.get("detail") or result.get("error_message") or "unknown_error",
    }


def _aggregate_pipeline_audio_status(profiles: dict[str, dict]) -> str:
    statuses = [p["status"] for p in profiles.values()]
    ready_count = sum(1 for s in statuses if s == "ready")
    if ready_count == len(statuses):
        return "success"
    if ready_count > 0:
        return "partial_success"
    if all(s == "skipped" for s in statuses):
        return "skipped"
    return "failed"


def _skipped_profiles_payload(reason: str) -> dict[str, dict]:
    return {
        VOICE_PROFILE_FEMALE: {"status": "skipped", "error_message": reason},
        VOICE_PROFILE_MALE: {"status": "skipped", "error_message": reason},
    }


def generate_all_narrative_audio_variants(
    report_date: date | None,
    *,
    narrative_result: dict | None = None,
) -> dict:
    """
    Generate female and male TTS variants for a ready narrative.

    Reuses generate_narrative_audio per profile — run concurrently (2026-07-06
    speed pass) since each profile writes to a distinct file path and a
    distinct (narrative_id, voice_profile) DB row, with no shared mutable
    state between them. Does not fail the whole batch when one profile fails.
    """
    date_str = str(report_date) if report_date else None
    ready, skip_reason = narrative_ready_for_audio_generation(narrative_result)
    if not ready:
        reason = skip_reason or "narrative_not_ready"
        return {
            "status": "skipped",
            "reason": reason,
            "report_date": date_str,
            "profiles": _skipped_profiles_payload(reason),
        }

    _log("voice_auto_generation_started", report_date=date_str)

    def _generate_for_profile(profile: str) -> dict:
        return generate_narrative_audio(
            report_date,
            regenerate=False,
            voice_profile=profile,
        )

    with ThreadPoolExecutor(max_workers=len(_PIPELINE_VOICE_PROFILES)) as executor:
        results = list(executor.map(_generate_for_profile, _PIPELINE_VOICE_PROFILES))

    profiles: dict[str, dict] = {}
    last_report_date = date_str
    for profile, result in zip(_PIPELINE_VOICE_PROFILES, results):
        if result.get("report_date"):
            last_report_date = result["report_date"]
        profiles[profile] = _profile_summary_from_result(result)
        _log(
            "voice_auto_generation_profile_done",
            report_date=last_report_date,
            voice_profile=profile,
            status=profiles[profile]["status"],
        )

    aggregate = _aggregate_pipeline_audio_status(profiles)
    out: dict = {
        "status": aggregate,
        "report_date": last_report_date,
        "profiles": profiles,
    }
    if aggregate == "skipped":
        out["reason"] = "all_profiles_skipped"

    _log(
        "voice_auto_generation_finished",
        report_date=last_report_date,
        status=aggregate,
        female=profiles[VOICE_PROFILE_FEMALE]["status"],
        male=profiles[VOICE_PROFILE_MALE]["status"],
    )
    return out


def _sync_default_narrative_audio(
    cur,
    narrative_id: int,
    voice_profile: str,
    *,
    audio_status: str,
    audio_url: str | None = None,
    audio_storage_path: str | None = None,
    audio_duration_seconds: int | None = None,
    audio_provider_voice: str | None = None,
    audio_model: str | None = None,
    audio_generated_at: bool = False,
    audio_error_message: str | None = None,
) -> None:
    if voice_profile != get_default_voice_profile():
        return
    update_narrative_audio(
        cur,
        narrative_id,
        audio_status=audio_status,
        audio_url=audio_url,
        audio_storage_path=audio_storage_path,
        audio_duration_seconds=audio_duration_seconds,
        audio_voice=audio_provider_voice,
        audio_model=audio_model,
        audio_generated_at=audio_generated_at,
        audio_error_message=audio_error_message,
    )


def generate_narrative_audio(
    report_date: date | None = None,
    *,
    regenerate: bool = False,
    voice_profile: str | None = None,
    voice: str | None = None,
) -> dict:
    """
    Generate TTS audio for the latest ready daily narrative on a report date.

    Uses voice_profile (female/male) for product-facing generation. Legacy voice=
    accepts a provider voice name for backward compatibility.
    """
    target_date = report_date
    if target_date is None:
        try:
            conn_probe = get_connection()
            probe_cur = conn_probe.cursor()
            try:
                target_date = get_latest_daily_report_date(probe_cur) or date.today()
            finally:
                probe_cur.close()
                conn_probe.close()
        except ValueError:
            target_date = date.today()
    date_str = str(target_date)
    stage = "audio_generate_start"

    try:
        target_profile, target_voice = _resolve_generation_targets(voice_profile, voice)
    except ValueError as e:
        _pipeline_failed(stage, date_str, error=str(e)[:200])
        code = "invalid_voice_profile" if voice_profile else "invalid_voice"
        return {
            "status": "error",
            "code": code,
            "detail": str(e),
            "report_date": date_str,
        }

    try:
        conn = get_connection()
    except ValueError as e:
        _pipeline_failed(stage, date_str, error=str(e)[:200])
        return {"status": "error", "code": "db_config", "detail": str(e), "report_date": date_str}

    cur = conn.cursor()
    try:
        _pipeline(
            stage,
            date_str,
            regenerate=regenerate,
            voice_profile=target_profile,
        )

        stage = "load_narrative"
        row = get_ready_narrative_row(cur, target_date)
        if not row:
            _log("narrative_audio_skipped", report_date=date_str, reason="no_ready_narrative")
            return {
                "status": "skipped",
                "reason": "no_ready_narrative",
                "report_date": date_str,
            }

        narrative_id = row["id"]
        version = row["version"]
        scope = row["scope"]
        variant_row = get_audio_variant_row(cur, narrative_id, target_profile)
        _pipeline(stage, date_str, narrative_id=narrative_id, version=version)

        if (
            not regenerate
            and variant_row
            and _variant_ready_for_version(
                variant_row,
                scope=scope,
                date_str=date_str,
                version=version,
                voice_profile=target_profile,
            )
        ):
            _log("narrative_audio_skipped", report_date=date_str, reason="ready_audio_exists")
            return {
                "status": "skipped",
                "reason": "ready_audio_exists",
                "report_date": date_str,
                "narrative_id": narrative_id,
                "voice_profile": target_profile,
                "audio_url": variant_row.get("audio_url"),
                "audio_duration_seconds": variant_row.get("audio_duration_seconds"),
            }

        upsert_audio_variant(
            cur,
            narrative_id,
            target_profile,
            audio_status="generating",
            audio_error_message=None,
        )
        conn.commit()

        stage = "prepare_text"
        prepared_text = prepare_script_for_tts(row.get("script_text") or "")
        _pipeline(stage, date_str, chars=len(prepared_text))
        if not prepared_text:
            msg = "Prepared script text is empty after normalization."
            _pipeline_failed(stage, date_str, narrative_id=narrative_id, error=msg)
            _mark_variant_failed(cur, narrative_id, target_profile, msg)
            conn.commit()
            return {
                "status": "failed",
                "report_date": date_str,
                "narrative_id": narrative_id,
                "voice_profile": target_profile,
                "error_message": msg,
                "failed_stage": stage,
            }

        storage_mode = get_audio_storage_mode()
        if storage_mode not in ("local", "supabase"):
            msg = (
                f"Unsupported VOICE_AUDIO_STORAGE: {storage_mode}. "
                "Use 'local' or 'supabase'."
            )
            _pipeline_failed(stage, date_str, narrative_id=narrative_id, error=msg)
            _mark_variant_failed(cur, narrative_id, target_profile, msg)
            conn.commit()
            return {
                "status": "failed",
                "report_date": date_str,
                "narrative_id": narrative_id,
                "voice_profile": target_profile,
                "error_message": msg,
                "failed_stage": stage,
            }

        stage = "tts_request_start"
        _pipeline(stage, date_str, narrative_id=narrative_id)

        try:
            audio_bytes, model, used_voice = synthesize_speech(prepared_text, voice=target_voice)
        except TTSConfigurationError as e:
            _pipeline_failed(
                "tts_request_start",
                date_str,
                narrative_id=narrative_id,
                error_type=e.category.value,
            )
            return {
                "status": "error",
                "code": "no_api_key",
                "detail": e.public_message,
                "report_date": date_str,
                "narrative_id": narrative_id,
                "voice_profile": target_profile,
                "failed_stage": "tts_request_start",
            }
        except TTSGenerationError as e:
            public_msg = e.public_message
            _mark_variant_failed(cur, narrative_id, target_profile, public_msg)
            conn.commit()
            _pipeline_failed(
                "tts_request_start",
                date_str,
                narrative_id=narrative_id,
                error_type=e.category.value,
                diagnostic=e.diagnostic_message[:200],
            )
            return {
                "status": "failed",
                "report_date": date_str,
                "narrative_id": narrative_id,
                "voice_profile": target_profile,
                "error_message": public_msg,
                "error_type": e.category.value,
                "failed_stage": "tts_request_start",
            }

        stage = "tts_request_success"
        _pipeline(stage, date_str, narrative_id=narrative_id, bytes=len(audio_bytes), model=model)

        word_fallback = estimate_duration_from_words(prepared_text)
        duration_seconds = estimate_mp3_duration_seconds(audio_bytes, word_fallback)
        quality = validate_audio_file(audio_bytes, duration_seconds)

        if not quality["passed"]:
            msg = "; ".join(quality.get("errors") or [])
            stage = "quality_gate"
            _pipeline_failed(stage, date_str, narrative_id=narrative_id, error=msg)
            _mark_variant_failed(cur, narrative_id, target_profile, msg)
            conn.commit()
            return {
                "status": "failed",
                "report_date": date_str,
                "narrative_id": narrative_id,
                "voice_profile": target_profile,
                "error_message": msg,
                "quality_gate": quality,
                "failed_stage": stage,
            }

        stage = "audio_write_start"
        storage_path = build_storage_path(scope, date_str, version, target_profile)
        _pipeline(stage, date_str, path=str(storage_path))
        save_audio_bytes(storage_path, audio_bytes)
        public_url = build_public_url(scope, date_str, version, target_profile)

        stage = "audio_write_success"
        _pipeline(stage, date_str, path=str(storage_path))

        stage = "database_update"
        upsert_audio_variant(
            cur,
            narrative_id,
            target_profile,
            audio_status="ready",
            audio_url=public_url,
            audio_storage_path=str(storage_path),
            audio_duration_seconds=duration_seconds,
            audio_provider_voice=used_voice,
            audio_model=model,
            audio_generated_at=True,
            audio_error_message=None,
        )
        _sync_default_narrative_audio(
            cur,
            narrative_id,
            target_profile,
            audio_status="ready",
            audio_url=public_url,
            audio_storage_path=str(storage_path),
            audio_duration_seconds=duration_seconds,
            audio_provider_voice=used_voice,
            audio_model=model,
            audio_generated_at=True,
            audio_error_message=None,
        )
        conn.commit()
        _pipeline(stage, date_str, narrative_id=narrative_id)

        stage = "finished"
        _pipeline(stage, date_str, narrative_id=narrative_id, duration=duration_seconds)
        return {
            "status": "success",
            "report_date": date_str,
            "narrative_id": narrative_id,
            "version": version,
            "voice_profile": target_profile,
            "audio_url": public_url,
            "audio_duration_seconds": duration_seconds,
            "audio_model": model,
            "quality_gate": quality,
        }

    except Exception as e:
        conn.rollback()
        _pipeline_failed(stage, date_str, error=str(e)[:300])
        return {
            "status": "error",
            "report_date": date_str,
            "detail": str(e)[:500],
            "failed_stage": stage,
        }
    finally:
        cur.close()
        conn.close()
