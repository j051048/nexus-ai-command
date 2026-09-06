-- Apply before deploying the artifact persistence boundary. No non-atomic fallback.
BEGIN;

CREATE OR REPLACE FUNCTION public.persist_artifact_package(
    p_organization_id uuid, p_user_id uuid, p_artifact jsonb, p_version jsonb,
    p_links jsonb, p_result jsonb, p_job_id uuid DEFAULT NULL,
    p_lease_token uuid DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public
AS $$
DECLARE
    artifact_id uuid := (p_artifact->>'id')::uuid;
    version_id uuid := (p_version->>'id')::uuid;
    job public.artifact_generation_jobs%ROWTYPE;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.organization_members
        WHERE organization_id = p_organization_id AND user_id = p_user_id
    ) OR (current_user <> 'service_role' AND (
        auth.uid() IS DISTINCT FROM p_user_id OR
        p_organization_id::text IS DISTINCT FROM public.current_tenant_id_text()
    )) THEN
        RAISE EXCEPTION 'artifact membership required' USING ERRCODE = '42501';
    END IF;
    IF (p_job_id IS NULL) <> (p_lease_token IS NULL) THEN
        RAISE EXCEPTION 'job and lease must be supplied together';
    END IF;
    IF p_job_id IS NOT NULL THEN
        SELECT * INTO job FROM public.artifact_generation_jobs
        WHERE id = p_job_id AND organization_id = p_organization_id
          AND created_by = p_user_id FOR UPDATE;
        IF NOT FOUND OR job.status <> 'running'
           OR job.lease_token IS DISTINCT FROM p_lease_token
           OR job.lease_expires_at IS NULL OR job.lease_expires_at <= now() THEN
            RAISE EXCEPTION 'artifact job lease lost' USING ERRCODE = '40001';
        END IF;
    END IF;
    IF p_result->>'id' IS DISTINCT FROM artifact_id::text THEN
        RAISE EXCEPTION 'artifact result identity mismatch';
    END IF;

    INSERT INTO public.artifacts (
        id, organization_id, created_by, artifact_code, title, artifact_type,
        audience, status, approval_status, quality_score, latest_version,
        source_request, metadata
    ) VALUES (
        artifact_id, p_organization_id, p_user_id, p_artifact->>'artifact_code',
        p_artifact->>'title', p_artifact->>'artifact_type', p_artifact->>'audience',
        p_artifact->>'status', p_artifact->>'approval_status',
        (p_artifact->>'quality_score')::numeric, 1,
        p_artifact->>'source_request', p_artifact->'metadata'
    );
    INSERT INTO public.artifact_versions (
        id, organization_id, artifact_id, version_number, content_markdown,
        quality_snapshot, evidence_snapshot, generation_metadata, created_by
    ) VALUES (
        version_id, p_organization_id, artifact_id, 1, p_version->>'content_markdown',
        p_version->'quality_snapshot', p_version->'evidence_snapshot',
        p_version->'generation_metadata', p_user_id
    );
    INSERT INTO public.artifact_evidence_links (
        organization_id, artifact_id, artifact_version_id, document_id,
        chunk_id, citation_id, source_title, source_version
    ) SELECT p_organization_id, artifact_id, version_id,
        item->>'document_id', item->>'chunk_id', item->>'citation_id',
        item->>'source_title', item->>'source_version'
      FROM jsonb_array_elements(COALESCE(p_links, '[]'::jsonb)) AS item;

    IF p_job_id IS NOT NULL THEN
        UPDATE public.artifact_generation_jobs SET
            status = 'completed', stage = 'completed', progress = 100,
            artifact_id = persist_artifact_package.artifact_id, result_payload = p_result,
            completed_at = now(), updated_at = now(), lease_token = NULL,
            lease_expires_at = NULL, worker_id = NULL
        WHERE id = p_job_id;
    END IF;
    RETURN artifact_id;
END;
$$;
REVOKE ALL ON FUNCTION public.persist_artifact_package(uuid, uuid, jsonb, jsonb, jsonb, jsonb, uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.persist_artifact_package(uuid, uuid, jsonb, jsonb, jsonb, jsonb, uuid, uuid) TO authenticated, service_role;

DROP POLICY IF EXISTS artifact_jobs_actor_guard ON public.artifact_generation_jobs;
CREATE POLICY artifact_jobs_actor_guard ON public.artifact_generation_jobs
AS RESTRICTIVE FOR ALL TO authenticated
USING (created_by = auth.uid()) WITH CHECK (created_by = auth.uid());

COMMIT;
