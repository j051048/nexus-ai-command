-- Artifact quality platform: golden template library, LLM judge snapshot,
-- feedback diff learning, and SLO observability columns.
-- Additive only; application behavior does not depend on telemetry.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.artifact_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    template_key text NOT NULL,
    artifact_type text NOT NULL,
    instrument_line text,
    industry text,
    title text NOT NULL,
    sections jsonb NOT NULL DEFAULT '[]'::jsonb,
    content_markdown text NOT NULL DEFAULT '',
    version text NOT NULL DEFAULT '1.0.0',
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'draft', 'archived')),
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, template_key, version)
);

CREATE INDEX IF NOT EXISTS idx_artifact_templates_lookup
    ON public.artifact_templates
        (organization_id, artifact_type, instrument_line, industry, created_at DESC);

-- Quality events now carry the winning template key (for A/B) and the LLM
-- judge snapshot used for the hybrid score.
ALTER TABLE public.agent_artifact_quality_events
    ADD COLUMN IF NOT EXISTS template_key text,
    ADD COLUMN IF NOT EXISTS judge_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_agent_artifact_quality_template
    ON public.agent_artifact_quality_events
        (organization_id, template_key, created_at DESC)
    WHERE template_key IS NOT NULL;

-- Human-feedback events now carry the edit diff (learning signal).
ALTER TABLE public.artifact_feedback_events
    ADD COLUMN IF NOT EXISTS diff_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS learning_status text NOT NULL DEFAULT 'recorded'
        CHECK (learning_status IN ('recorded', 'review_candidate', 'approved', 'rejected'));

CREATE INDEX IF NOT EXISTS idx_artifact_feedback_learning_queue
    ON public.artifact_feedback_events
        (organization_id, learning_status, created_at DESC)
    WHERE learning_status = 'review_candidate';

ALTER TABLE public.artifact_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS artifact_templates_tenant_isolation
    ON public.artifact_templates;
CREATE POLICY artifact_templates_tenant_isolation
    ON public.artifact_templates
    FOR ALL
    USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
