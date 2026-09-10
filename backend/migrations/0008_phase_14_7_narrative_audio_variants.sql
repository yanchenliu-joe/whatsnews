-- Phase 14.7: Per-profile (male/female) narrative audio variants
-- Run once in Supabase SQL Editor. Safe to re-run.

CREATE TABLE IF NOT EXISTS narrative_audio_variants (
    id                      BIGSERIAL PRIMARY KEY,
    narrative_id            BIGINT NOT NULL REFERENCES briefing_narratives(id) ON DELETE CASCADE,
    voice_profile           TEXT NOT NULL CHECK (voice_profile IN ('female', 'male')),
    audio_status            TEXT NOT NULL DEFAULT 'not_generated',
    audio_url               TEXT,
    audio_storage_path      TEXT,
    audio_duration_seconds  INTEGER,
    audio_provider_voice    TEXT,
    audio_model             TEXT,
    audio_generated_at      TIMESTAMPTZ,
    audio_error_message     TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (narrative_id, voice_profile)
);

CREATE INDEX IF NOT EXISTS idx_narrative_audio_variants_narrative
    ON narrative_audio_variants (narrative_id);

-- Backfill existing single-track audio as the female profile variant.
INSERT INTO narrative_audio_variants (
    narrative_id,
    voice_profile,
    audio_status,
    audio_url,
    audio_storage_path,
    audio_duration_seconds,
    audio_provider_voice,
    audio_model,
    audio_generated_at,
    audio_error_message
)
SELECT
    id,
    'female',
    audio_status,
    audio_url,
    audio_storage_path,
    audio_duration_seconds,
    audio_voice,
    audio_model,
    audio_generated_at,
    audio_error_message
FROM briefing_narratives
WHERE scope = 'daily'
  AND topic_id IS NULL
  AND (audio_url IS NOT NULL OR audio_status NOT IN ('not_generated', ''))
ON CONFLICT (narrative_id, voice_profile) DO NOTHING;
