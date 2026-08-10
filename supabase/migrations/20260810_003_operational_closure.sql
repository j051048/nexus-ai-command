-- Production closure for durable artifact jobs, recoverable knowledge ingestion,
-- delivery outcome telemetry, and conservative migration-history reconciliation.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.migration_history (
    id bigserial PRIMARY KEY,
    migration_name text NOT NULL UNIQUE,
    applied_at timestamptz NOT NULL DEFAULT now(),
    checksum text NOT NULL DEFAULT ''
);

ALTER TABLE public.artifact_generation_jobs
    ADD COLUMN IF NOT EXISTS lease_token uuid,
    ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS heartbeat_at timestamptz,
    ADD COLUMN IF NOT EXISTS worker_id text,
    ADD COLUMN IF NOT EXISTS recovery_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_recovered_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_artifact_generation_jobs_lease
    ON public.artifact_generation_jobs (lease_expires_at)
    WHERE status IN ('running', 'cancelling');

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS source_storage_path text,
    ADD COLUMN IF NOT EXISTS source_content_type text,
    ADD COLUMN IF NOT EXISTS ingestion_attempt integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ingestion_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS ingestion_error_code text;

CREATE INDEX IF NOT EXISTS idx_documents_ingestion_state
    ON public.documents (organization_id, status, ingestion_updated_at DESC);

DO $$
BEGIN
    IF to_regclass('storage.buckets') IS NOT NULL THEN
        INSERT INTO storage.buckets (id, name, public)
        VALUES ('documents', 'documents', false)
        ON CONFLICT (id) DO NOTHING;
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.artifact_delivery_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    artifact_id uuid NOT NULL REFERENCES public.artifacts(id) ON DELETE CASCADE,
    artifact_version_id uuid REFERENCES public.artifact_versions(id) ON DELETE SET NULL,
    user_id uuid,
    event_type text NOT NULL CHECK (
        event_type IN ('generated', 'downloaded', 'reviewed', 'used', 'edited', 'discarded', 'won', 'lost')
    ),
    output_format text,
    estimated_value numeric(14, 2),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artifact_delivery_events_org_time
    ON public.artifact_delivery_events (organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_delivery_events_artifact
    ON public.artifact_delivery_events (artifact_id, created_at DESC);

ALTER TABLE public.artifact_delivery_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS artifact_delivery_events_tenant_isolation
    ON public.artifact_delivery_events;
CREATE POLICY artifact_delivery_events_tenant_isolation
    ON public.artifact_delivery_events
    FOR ALL
    USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

CREATE OR REPLACE FUNCTION public.claim_artifact_generation_job(
    p_job_id uuid,
    p_worker_id text,
    p_lease_seconds integer DEFAULT 90
)
RETURNS SETOF public.artifact_generation_jobs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    UPDATE public.artifact_generation_jobs AS job
    SET status = 'running',
        stage = CASE WHEN job.status = 'queued' THEN 'starting' ELSE job.stage END,
        progress = GREATEST(job.progress, 2),
        attempt = job.attempt + 1,
        started_at = COALESCE(job.started_at, now()),
        lease_token = gen_random_uuid(),
        lease_expires_at = now() + make_interval(secs => GREATEST(30, LEAST(p_lease_seconds, 900))),
        heartbeat_at = now(),
        worker_id = left(COALESCE(p_worker_id, 'worker'), 200),
        error_code = NULL,
        error_message = NULL,
        updated_at = now()
    WHERE job.id = p_job_id
      AND job.attempt < job.max_attempts
      AND (
          job.status = 'queued'
          OR (
              job.status = 'running'
              AND (job.lease_expires_at IS NULL OR job.lease_expires_at < now())
          )
      )
    RETURNING job.*;
END;
$$;

CREATE OR REPLACE FUNCTION public.recover_stale_artifact_generation_jobs()
RETURNS SETOF public.artifact_generation_jobs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    UPDATE public.artifact_generation_jobs AS job
    SET status = 'cancelled',
        stage = 'cancelled',
        completed_at = now(),
        lease_token = NULL,
        lease_expires_at = NULL,
        worker_id = NULL,
        updated_at = now()
    WHERE job.status = 'cancelling'
      AND (job.lease_expires_at IS NULL OR job.lease_expires_at < now())
    RETURNING job.*;

    RETURN QUERY
    UPDATE public.artifact_generation_jobs AS job
    SET status = CASE WHEN job.attempt >= job.max_attempts THEN 'failed' ELSE 'queued' END,
        stage = CASE WHEN job.attempt >= job.max_attempts THEN 'failed' ELSE 'recovered' END,
        error_code = CASE WHEN job.attempt >= job.max_attempts THEN 'WORKER_LEASE_EXHAUSTED' ELSE NULL END,
        error_message = CASE WHEN job.attempt >= job.max_attempts THEN '任务执行节点多次中断，请人工重试' ELSE NULL END,
        completed_at = CASE WHEN job.attempt >= job.max_attempts THEN now() ELSE NULL END,
        queued_at = CASE WHEN job.attempt < job.max_attempts THEN now() ELSE job.queued_at END,
        celery_task_id = NULL,
        lease_token = NULL,
        lease_expires_at = NULL,
        worker_id = NULL,
        recovery_count = job.recovery_count + 1,
        last_recovered_at = now(),
        updated_at = now()
    WHERE job.status = 'running'
      AND (job.lease_expires_at IS NULL OR job.lease_expires_at < now())
    RETURNING job.*;
END;
$$;

CREATE OR REPLACE FUNCTION public.recover_stale_knowledge_ingestion(
    p_stale_minutes integer DEFAULT 15,
    p_limit integer DEFAULT 100
)
RETURNS SETOF public.documents
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    WITH stale AS (
        SELECT document.id
        FROM public.documents AS document
        WHERE document.source_storage_path IS NOT NULL
          AND document.status IN ('pending', 'processing')
          AND COALESCE(document.ingestion_updated_at, document.updated_at, document.created_at)
              < now() - make_interval(mins => GREATEST(5, LEAST(p_stale_minutes, 1440)))
        ORDER BY COALESCE(document.ingestion_updated_at, document.updated_at, document.created_at)
        FOR UPDATE SKIP LOCKED
        LIMIT GREATEST(1, LEAST(p_limit, 500))
    )
    UPDATE public.documents AS document
    SET status = 'pending',
        stage = 'recovered',
        progress = LEAST(COALESCE(document.progress, 0), 5),
        ingestion_updated_at = now(),
        ingestion_error_code = 'WORKER_STALE_RECOVERED',
        updated_at = now()
    FROM stale
    WHERE document.id = stale.id
    RETURNING document.*;
END;
$$;

CREATE OR REPLACE FUNCTION public.reconcile_migration_history(
    p_migration_name text,
    p_checksum text,
    p_required_tables text[] DEFAULT '{}'::text[],
    p_required_columns jsonb DEFAULT '{}'::jsonb,
    p_apply boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    required_table text;
    required_column text;
    column_list jsonb;
    missing_tables text[] := '{}'::text[];
    missing_columns text[] := '{}'::text[];
    existing_checksum text;
BEGIN
    IF COALESCE(trim(p_migration_name), '') = '' OR COALESCE(trim(p_checksum), '') = '' THEN
        RAISE EXCEPTION 'migration name and checksum are required';
    END IF;

    FOREACH required_table IN ARRAY COALESCE(p_required_tables, '{}'::text[]) LOOP
        IF to_regclass(format('public.%I', required_table)) IS NULL THEN
            missing_tables := array_append(missing_tables, required_table);
        END IF;
    END LOOP;

    FOR required_table, column_list IN
        SELECT key, value FROM jsonb_each(COALESCE(p_required_columns, '{}'::jsonb))
    LOOP
        FOR required_column IN SELECT jsonb_array_elements_text(column_list)
        LOOP
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = required_table
                  AND column_name = required_column
            ) THEN
                missing_columns := array_append(
                    missing_columns,
                    required_table || '.' || required_column
                );
            END IF;
        END LOOP;
    END LOOP;

    SELECT checksum INTO existing_checksum
    FROM public.migration_history
    WHERE migration_name = p_migration_name;

    IF COALESCE(existing_checksum, '') <> '' AND existing_checksum <> p_checksum THEN
        RAISE EXCEPTION 'checksum drift for migration %', p_migration_name;
    END IF;

    IF p_apply AND cardinality(missing_tables) = 0 AND cardinality(missing_columns) = 0 THEN
        INSERT INTO public.migration_history (migration_name, checksum)
        VALUES (p_migration_name, p_checksum)
        ON CONFLICT (migration_name) DO UPDATE
        SET checksum = EXCLUDED.checksum
        WHERE public.migration_history.checksum = '';
    END IF;

    RETURN jsonb_build_object(
        'migration_name', p_migration_name,
        'verified', cardinality(missing_tables) = 0 AND cardinality(missing_columns) = 0,
        'recorded', p_apply AND cardinality(missing_tables) = 0 AND cardinality(missing_columns) = 0,
        'already_recorded', existing_checksum IS NOT NULL,
        'missing_tables', to_jsonb(missing_tables),
        'missing_columns', to_jsonb(missing_columns)
    );
END;
$$;

REVOKE ALL ON FUNCTION public.claim_artifact_generation_job(uuid, text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.recover_stale_artifact_generation_jobs() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.recover_stale_knowledge_ingestion(integer, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reconcile_migration_history(text, text, text[], jsonb, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.claim_artifact_generation_job(uuid, text, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.recover_stale_artifact_generation_jobs() TO service_role;
GRANT EXECUTE ON FUNCTION public.recover_stale_knowledge_ingestion(integer, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.reconcile_migration_history(text, text, text[], jsonb, boolean) TO service_role;
