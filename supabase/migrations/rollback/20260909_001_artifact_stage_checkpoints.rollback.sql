-- First roll back application workers; dropping checkpoints discards saved work.
BEGIN;
DROP FUNCTION IF EXISTS public.artifact_stage_checkpoint(uuid, uuid, uuid, uuid, text, text, jsonb);
DROP TABLE IF EXISTS public.artifact_stage_checkpoints;
COMMIT;
