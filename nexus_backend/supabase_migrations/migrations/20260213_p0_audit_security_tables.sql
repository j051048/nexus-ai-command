-- P0/P1 Audit Fix Migration: Security-related schema additions
-- This migration adds tables and columns required by the 14-dimension audit fixes.

-- ============================================================================
-- 1. OAuth Tokens Table (Phase 5.2 - Token Persistence)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.oauth_tokens (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    token_hash    TEXT NOT NULL UNIQUE,
    refresh_token_hash TEXT,
    client_id     TEXT NOT NULL,
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    scopes        JSONB DEFAULT '[]'::jsonb,
    expires_at    BIGINT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),
    revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_oauth_tokens_token_hash
    ON public.oauth_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_client_user
    ON public.oauth_tokens (client_id, user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_expires
    ON public.oauth_tokens (expires_at);

-- RLS
ALTER TABLE public.oauth_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY oauth_tokens_service_key ON public.oauth_tokens
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================================
-- 2. Embedding Model Version Tracking (Phase 5.5)
-- ============================================================================

-- Add embedding model metadata columns to documents table if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'documents'
          AND column_name = 'embedding_model'
    ) THEN
        ALTER TABLE public.documents ADD COLUMN embedding_model TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'documents'
          AND column_name = 'embedding_model_version'
    ) THEN
        ALTER TABLE public.documents ADD COLUMN embedding_model_version TEXT;
    END IF;
END $$;

-- ============================================================================
-- 3. Webhook Delivery Log (Phase 5.1 - Replay Attack Prevention)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.webhook_delivery_log (
    id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    webhook_id     UUID,
    event_type     TEXT NOT NULL,
    payload_hash   TEXT NOT NULL,
    signature      TEXT NOT NULL,
    status_code    INT,
    delivered_at   TIMESTAMPTZ DEFAULT now(),
    response_body  TEXT
);

CREATE INDEX IF NOT EXISTS idx_webhook_delivery_timestamp
    ON public.webhook_delivery_log (delivered_at DESC);

-- ============================================================================
-- DOWN (rollback)
-- ============================================================================
-- To rollback, run the following manually:
--
-- DROP TABLE IF EXISTS public.webhook_delivery_log;
-- ALTER TABLE public.documents DROP COLUMN IF EXISTS embedding_model;
-- ALTER TABLE public.documents DROP COLUMN IF EXISTS embedding_model_version;
-- DROP TABLE IF EXISTS public.oauth_tokens;
