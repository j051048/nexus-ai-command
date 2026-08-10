-- Server-owned activation state and explainable knowledge readiness metadata.

CREATE TABLE IF NOT EXISTS public.organization_activation_state (
    organization_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
    step text NOT NULL DEFAULT 'knowledge'
        CHECK (step IN ('knowledge', 'organize', 'review', 'first_value', 'complete')),
    company_name text NOT NULL DEFAULT '',
    instrument_families text[] NOT NULL DEFAULT '{}',
    markets text NOT NULL DEFAULT '',
    uploaded_document_count integer NOT NULL DEFAULT 0 CHECK (uploaded_document_count >= 0),
    uploaded_file_names text[] NOT NULL DEFAULT '{}',
    facts_confirmed boolean NOT NULL DEFAULT false,
    first_outcome text CHECK (first_outcome IS NULL OR first_outcome IN ('solution', 'tender', 'opportunity')),
    first_artifact_id uuid REFERENCES public.artifacts(id) ON DELETE SET NULL,
    completed_at timestamptz,
    dismissed_until timestamptz,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.organization_activation_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organization_activation_state_tenant_access
    ON public.organization_activation_state;
CREATE POLICY organization_activation_state_tenant_access
    ON public.organization_activation_state
    FOR ALL
    USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

CREATE INDEX IF NOT EXISTS idx_organization_activation_step
    ON public.organization_activation_state (step, updated_at DESC);

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS readiness_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS extraction_version text,
    ADD COLUMN IF NOT EXISTS content_fingerprint text;
