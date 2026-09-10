-- Phase 29: RevenueCat entitlements table.
-- Run once in the Supabase SQL Editor. Safe to re-run (idempotent).
--
-- Tracks premium subscription status per authenticated user (profiles.id),
-- kept in sync via POST /webhooks/revenuecat. Entitlement is identified by
-- the Supabase auth user id, not a device id or RevenueCat's own anonymous
-- app_user_id — the mobile client calls Purchases.logIn(supabaseUserId)
-- after sign-in so RevenueCat's app_user_id matches profiles.id.
--
-- is_active + expires_at together determine current premium status:
-- a row can be is_active=TRUE with a past expires_at right after expiry,
-- until the next webhook (e.g. EXPIRATION) confirms it — callers should
-- treat premium as: is_active AND (expires_at IS NULL OR expires_at > NOW()).

CREATE TABLE IF NOT EXISTS entitlements (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    entitlement_id      TEXT NOT NULL DEFAULT 'premium',
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
    product_id          TEXT,
    store               TEXT,
    expires_at          TIMESTAMPTZ,
    last_event_type     TEXT,
    last_event_at       TIMESTAMPTZ,
    raw_event           JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, entitlement_id)
);

CREATE INDEX IF NOT EXISTS idx_entitlements_user_id ON entitlements (user_id);
