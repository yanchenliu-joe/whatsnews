-- Phase 14.2: Narrative TTS audio metadata on briefing_narratives
-- Run once in Supabase SQL Editor. Safe to re-run.

ALTER TABLE briefing_narratives
    ADD COLUMN IF NOT EXISTS audio_status TEXT NOT NULL DEFAULT 'not_generated',
    ADD COLUMN IF NOT EXISTS audio_url TEXT,
    ADD COLUMN IF NOT EXISTS audio_storage_path TEXT,
    ADD COLUMN IF NOT EXISTS audio_duration_seconds INTEGER,
    ADD COLUMN IF NOT EXISTS audio_voice TEXT,
    ADD COLUMN IF NOT EXISTS audio_model TEXT,
    ADD COLUMN IF NOT EXISTS audio_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS audio_error_message TEXT;

CREATE INDEX IF NOT EXISTS idx_briefing_narratives_audio_status
    ON briefing_narratives (report_date DESC, audio_status);
