-- Memory trust, lifecycle, atomic versioning, and durable extraction jobs.

ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS lifecycle_state TEXT NOT NULL DEFAULT 'active'
        CHECK (lifecycle_state IN (
            'proposed', 'confirmed', 'active', 'pending_review',
            'superseded', 'expired', 'rejected', 'archived'
        )),
    ADD COLUMN IF NOT EXISTS sensitivity TEXT NOT NULL DEFAULT 'internal'
        CHECK (sensitivity IN ('public', 'internal', 'confidential', 'restricted')),
    ADD COLUMN IF NOT EXISTS provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS evidence_ref TEXT;

-- Reconcile historical forks before enforcing one current version per key.
WITH ranked AS (
    SELECT id,
           first_value(id) OVER (
               PARTITION BY organization_id, user_id, key
               ORDER BY version DESC NULLS LAST, created_at DESC, id DESC
           ) AS newest_id,
           row_number() OVER (
               PARTITION BY organization_id, user_id, key
               ORDER BY version DESC NULLS LAST, created_at DESC, id DESC
           ) AS row_num
    FROM public.conversation_memories
    WHERE superseded_by IS NULL
      AND lifecycle_state IN ('proposed', 'confirmed', 'active', 'pending_review')
)
UPDATE public.conversation_memories AS memory
SET superseded_by = ranked.newest_id,
    lifecycle_state = 'superseded',
    updated_at = now()
FROM ranked
WHERE memory.id = ranked.id
  AND ranked.row_num > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_memories_current_key
    ON public.conversation_memories(organization_id, user_id, key)
    WHERE superseded_by IS NULL
      AND lifecycle_state IN ('proposed', 'confirmed', 'active', 'pending_review');

CREATE INDEX IF NOT EXISTS idx_conversation_memories_lifecycle
    ON public.conversation_memories(organization_id, user_id, lifecycle_state, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversation_memories_expiry
    ON public.conversation_memories(expires_at)
    WHERE expires_at IS NOT NULL AND lifecycle_state IN ('confirmed', 'active');

CREATE TABLE IF NOT EXISTS public.memory_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    old_value_hash TEXT,
    new_value_hash TEXT,
    old_value_preview TEXT,
    new_value_preview TEXT,
    reason TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    source TEXT,
    extraction_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.memory_audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memory_audit_owner_read ON public.memory_audit_log;
CREATE POLICY memory_audit_owner_read
    ON public.memory_audit_log FOR SELECT
    USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_memory_audit_memory_created
    ON public.memory_audit_log(memory_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.memory_persistence_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'dead_letter')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.memory_persistence_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memory_jobs_owner_read ON public.memory_persistence_jobs;
CREATE POLICY memory_jobs_owner_read
    ON public.memory_persistence_jobs FOR SELECT
    USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_memory_jobs_ready
    ON public.memory_persistence_jobs(status, available_at, created_at)
    WHERE status IN ('queued', 'failed');

CREATE OR REPLACE FUNCTION public.claim_memory_persistence_job(p_job_id UUID)
RETURNS SETOF public.memory_persistence_jobs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    claimed public.memory_persistence_jobs%ROWTYPE;
BEGIN
    SELECT * INTO claimed
    FROM public.memory_persistence_jobs
    WHERE (p_job_id IS NULL OR id = p_job_id)
      AND status IN ('queued', 'failed')
      AND available_at <= now()
    ORDER BY created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF claimed.id IS NULL THEN
        RETURN;
    END IF;

    UPDATE public.memory_persistence_jobs
    SET status = 'processing', attempts = attempts + 1,
        locked_at = now(), updated_at = now()
    WHERE id = claimed.id
    RETURNING * INTO claimed;

    RETURN NEXT claimed;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_memory_persistence_job(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_memory_persistence_job(UUID) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.claim_memory_persistence_job(UUID) TO service_role;

CREATE OR REPLACE FUNCTION public.upsert_conversation_memory_version(
    p_user_id UUID,
    p_organization_id UUID,
    p_category TEXT,
    p_key TEXT,
    p_value TEXT,
    p_metadata JSONB,
    p_importance DOUBLE PRECISION,
    p_embedding vector,
    p_enriched_value TEXT,
    p_valid_from TIMESTAMPTZ,
    p_valid_until TIMESTAMPTZ,
    p_pattern_key TEXT,
    p_fact_type TEXT,
    p_confidence DOUBLE PRECISION,
    p_visibility TEXT,
    p_semantic_tags TEXT[],
    p_lifecycle_state TEXT,
    p_sensitivity TEXT,
    p_provenance JSONB,
    p_expires_at TIMESTAMPTZ,
    p_evidence_ref TEXT
)
RETURNS SETOF public.conversation_memories
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    previous_record public.conversation_memories%ROWTYPE;
    new_record public.conversation_memories%ROWTYPE;
    next_version INTEGER := 1;
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtextextended(p_organization_id::text || ':' || p_user_id::text || ':' || p_key, 0)
    );

    SELECT * INTO previous_record
    FROM public.conversation_memories
    WHERE organization_id = p_organization_id
      AND user_id = p_user_id
      AND key = p_key
      AND superseded_by IS NULL
      AND lifecycle_state IN ('proposed', 'confirmed', 'active', 'pending_review')
    ORDER BY version DESC NULLS LAST, created_at DESC
    LIMIT 1
    FOR UPDATE;

    IF FOUND THEN
        next_version := COALESCE(previous_record.version, 0) + 1;
        UPDATE public.conversation_memories
        SET lifecycle_state = 'superseded', updated_at = now()
        WHERE id = previous_record.id;
    END IF;

    INSERT INTO public.conversation_memories (
        user_id, organization_id, category, key, value, metadata, importance,
        embedding, enriched_value, valid_from, valid_until, pattern_key,
        fact_type, confidence, visibility, semantic_tags, version,
        lifecycle_state, sensitivity, provenance, expires_at, evidence_ref,
        access_count, last_accessed_at, created_at, updated_at
    ) VALUES (
        p_user_id, p_organization_id, p_category, p_key, p_value,
        COALESCE(p_metadata, '{}'::jsonb), p_importance, p_embedding,
        p_enriched_value, p_valid_from, p_valid_until, p_pattern_key,
        p_fact_type, p_confidence, p_visibility, COALESCE(p_semantic_tags, '{}'),
        next_version, p_lifecycle_state, p_sensitivity,
        COALESCE(p_provenance, '{}'::jsonb), p_expires_at, p_evidence_ref,
        0, now(), now(), now()
    ) RETURNING * INTO new_record;

    IF previous_record.id IS NOT NULL THEN
        UPDATE public.conversation_memories
        SET superseded_by = new_record.id, updated_at = now()
        WHERE id = previous_record.id;
    END IF;

    RETURN NEXT new_record;
END;
$$;

-- Keep unconfirmed, expired and superseded memories out of semantic recall.
CREATE OR REPLACE FUNCTION public.search_memories_by_embedding(
    query_embedding vector(1536),
    match_user_id UUID,
    match_limit INT DEFAULT 5,
    match_org_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID, user_id UUID, organization_id UUID, category TEXT, key TEXT,
    value TEXT, metadata JSONB, importance FLOAT, access_count INTEGER,
    last_accessed_at TIMESTAMPTZ, created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ, similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT cm.id, cm.user_id, cm.organization_id, cm.category, cm.key,
           cm.value, cm.metadata, cm.importance, cm.access_count,
           cm.last_accessed_at, cm.created_at, cm.updated_at,
           1 - (cm.embedding <=> query_embedding) AS similarity
    FROM public.conversation_memories cm
    WHERE cm.user_id = match_user_id
      AND cm.embedding IS NOT NULL
      AND cm.superseded_by IS NULL
      AND cm.lifecycle_state IN ('active', 'confirmed')
      AND (cm.expires_at IS NULL OR cm.expires_at > now())
      AND (match_org_id IS NULL OR cm.organization_id = match_org_id)
      AND 1 - (cm.embedding <=> query_embedding) > 0.3
    ORDER BY cm.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;
