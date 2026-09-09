-- Deploy before workers using artifact-stage checkpoints. No public payload API.
BEGIN;
CREATE TABLE IF NOT EXISTS public.artifact_stage_checkpoints (
    job_id uuid NOT NULL REFERENCES public.artifact_generation_jobs(id) ON DELETE CASCADE,
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by uuid NOT NULL,
    stage text NOT NULL CHECK (length(stage) BETWEEN 1 AND 100),
    input_hash text NOT NULL CHECK (length(input_hash) = 64),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 2000000),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, stage)
);
ALTER TABLE public.artifact_stage_checkpoints ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.artifact_stage_checkpoints FROM anon, authenticated;
GRANT ALL ON public.artifact_stage_checkpoints TO service_role;

CREATE OR REPLACE FUNCTION public.artifact_stage_checkpoint(
    p_organization_id uuid, p_user_id uuid, p_job_id uuid, p_lease_token uuid,
    p_stage text, p_input_hash text, p_payload jsonb DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = public
AS $$
DECLARE
    job public.artifact_generation_jobs%ROWTYPE;
    result jsonb;
BEGIN
    IF current_user <> 'service_role' OR NOT EXISTS (
        SELECT 1 FROM public.organization_members
        WHERE organization_id = p_organization_id AND user_id = p_user_id
    ) THEN
        RAISE EXCEPTION 'checkpoint membership required' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO job FROM public.artifact_generation_jobs
    WHERE id = p_job_id AND organization_id = p_organization_id
      AND created_by = p_user_id FOR UPDATE;
    IF NOT FOUND OR job.status <> 'running'
       OR job.lease_token IS DISTINCT FROM p_lease_token
       OR job.lease_expires_at IS NULL OR job.lease_expires_at <= now() THEN
        RAISE EXCEPTION 'checkpoint lease lost' USING ERRCODE = '40001';
    END IF;
    IF p_payload IS NOT NULL THEN
        INSERT INTO public.artifact_stage_checkpoints
            (job_id, organization_id, created_by, stage, input_hash, payload)
        VALUES (p_job_id, p_organization_id, p_user_id, p_stage, p_input_hash, p_payload)
        ON CONFLICT (job_id, stage) DO UPDATE SET
            input_hash = EXCLUDED.input_hash, payload = EXCLUDED.payload, updated_at = now();
    END IF;
    SELECT payload INTO result FROM public.artifact_stage_checkpoints
    WHERE job_id = p_job_id AND organization_id = p_organization_id
      AND created_by = p_user_id AND stage = p_stage AND input_hash = p_input_hash
      AND updated_at > now() - interval '7 days';
    RETURN result;
END;
$$;
REVOKE ALL ON FUNCTION public.artifact_stage_checkpoint(uuid, uuid, uuid, uuid, text, text, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.artifact_stage_checkpoint(uuid, uuid, uuid, uuid, text, text, jsonb) TO service_role;
COMMIT;
