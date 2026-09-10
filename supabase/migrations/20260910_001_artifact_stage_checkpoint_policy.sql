-- Additive repair: keep the checksum of the deployed checkpoint migration intact.
-- Checkpoints are worker-only. Actor, tenant and lease checks remain in the RPC.
BEGIN;

ALTER TABLE public.artifact_stage_checkpoints ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.artifact_stage_checkpoints FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.artifact_stage_checkpoints TO service_role;

DROP POLICY IF EXISTS artifact_stage_checkpoints_service_only
    ON public.artifact_stage_checkpoints;
CREATE POLICY artifact_stage_checkpoints_service_only
    ON public.artifact_stage_checkpoints
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

COMMIT;
