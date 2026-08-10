-- Durable artifact generation jobs for long-running, multi-stage delivery work.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.artifact_generation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by uuid,
    request_key text NOT NULL,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'cancelling', 'cancelled', 'completed', 'failed')),
    stage text NOT NULL DEFAULT 'queued',
    progress smallint NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    progress_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifact_id uuid REFERENCES public.artifacts(id) ON DELETE SET NULL,
    celery_task_id text,
    attempt smallint NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 10),
    max_attempts smallint NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    error_code text,
    error_message text,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, request_key)
);

CREATE INDEX IF NOT EXISTS idx_artifact_generation_jobs_queue
    ON public.artifact_generation_jobs (status, queued_at)
    WHERE status IN ('queued', 'running', 'cancelling');
CREATE INDEX IF NOT EXISTS idx_artifact_generation_jobs_org
    ON public.artifact_generation_jobs (organization_id, updated_at DESC);

ALTER TABLE public.artifact_generation_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS artifact_generation_jobs_tenant_isolation
    ON public.artifact_generation_jobs;
CREATE POLICY artifact_generation_jobs_tenant_isolation
    ON public.artifact_generation_jobs
    FOR ALL
    USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
