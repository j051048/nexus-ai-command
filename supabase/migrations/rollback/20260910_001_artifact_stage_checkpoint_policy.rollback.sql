-- Revert only the explicit policy; preserve RLS and worker-only privileges.
BEGIN;
DROP POLICY IF EXISTS artifact_stage_checkpoints_service_only
    ON public.artifact_stage_checkpoints;
COMMIT;
