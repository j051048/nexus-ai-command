-- Auditable quality events for externally usable Agent artifacts.
-- Events are append-only; application behavior does not depend on telemetry.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.agent_artifact_quality_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id uuid,
    session_id text,
    artifact_type text NOT NULL,
    skill_id text,
    skill_version text,
    score numeric(7, 3) NOT NULL CHECK (score BETWEEN 0 AND 100),
    ready boolean NOT NULL DEFAULT false,
    dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
    findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence_count integer NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    repair_count integer NOT NULL DEFAULT 0 CHECK (repair_count BETWEEN 0 AND 3),
    output_hash text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_artifact_quality_scope
    ON public.agent_artifact_quality_events
        (organization_id, artifact_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_artifact_quality_failures
    ON public.agent_artifact_quality_events
        (organization_id, created_at DESC)
    WHERE ready = false;

ALTER TABLE public.agent_artifact_quality_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_artifact_quality_select
    ON public.agent_artifact_quality_events;
CREATE POLICY agent_artifact_quality_select
    ON public.agent_artifact_quality_events
    FOR SELECT
    USING (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS agent_artifact_quality_insert
    ON public.agent_artifact_quality_events;
CREATE POLICY agent_artifact_quality_insert
    ON public.agent_artifact_quality_events
    FOR INSERT
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

REVOKE UPDATE, DELETE ON public.agent_artifact_quality_events FROM authenticated;

-- Human edits are recommendation-only learning candidates.  These additive
-- fields keep the quality delta and evidence snapshot without changing the
-- existing feedback API contract.
ALTER TABLE public.solution_feedback_events
    ADD COLUMN IF NOT EXISTS quality_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_fingerprint text,
    ADD COLUMN IF NOT EXISTS learning_status text NOT NULL DEFAULT 'recorded',
    ADD COLUMN IF NOT EXISTS content_similarity numeric(6, 5);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'solution_feedback_learning_status_check'
    ) THEN
        ALTER TABLE public.solution_feedback_events
            ADD CONSTRAINT solution_feedback_learning_status_check
            CHECK (learning_status IN ('recorded', 'review_candidate', 'approved', 'rejected'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_solution_feedback_learning_queue
    ON public.solution_feedback_events
        (organization_id, learning_status, created_at DESC)
    WHERE learning_status = 'review_candidate';
