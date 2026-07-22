-- Durable, tenant-safe delivery pipeline for AI-generated customer artifacts.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    created_by uuid,
    artifact_code text NOT NULL,
    title text NOT NULL,
    artifact_type text NOT NULL,
    audience text NOT NULL DEFAULT 'internal'
        CHECK (audience IN ('internal', 'customer', 'regulator', 'public')),
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'generating', 'review', 'needs_revision', 'approved', 'archived', 'failed')),
    approval_status text NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    quality_score numeric(7, 3) NOT NULL DEFAULT 0 CHECK (quality_score BETWEEN 0 AND 100),
    latest_version integer NOT NULL DEFAULT 1 CHECK (latest_version >= 1),
    source_request text NOT NULL DEFAULT '',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, artifact_code)
);

CREATE TABLE IF NOT EXISTS public.artifact_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    artifact_id uuid NOT NULL REFERENCES public.artifacts(id) ON DELETE CASCADE,
    version_number integer NOT NULL CHECK (version_number >= 1),
    content_markdown text NOT NULL,
    quality_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    generation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, version_number)
);

CREATE TABLE IF NOT EXISTS public.artifact_evidence_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    artifact_id uuid NOT NULL REFERENCES public.artifacts(id) ON DELETE CASCADE,
    artifact_version_id uuid NOT NULL REFERENCES public.artifact_versions(id) ON DELETE CASCADE,
    document_id text NOT NULL,
    chunk_id text NOT NULL,
    citation_id text NOT NULL,
    source_title text,
    source_version text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (artifact_version_id, citation_id)
);

CREATE TABLE IF NOT EXISTS public.artifact_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    artifact_id uuid NOT NULL REFERENCES public.artifacts(id) ON DELETE CASCADE,
    artifact_version_id uuid NOT NULL REFERENCES public.artifact_versions(id) ON DELETE CASCADE,
    reviewer_id uuid,
    decision text NOT NULL CHECK (decision IN ('approved', 'rejected')),
    notes text,
    confirmations jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.artifact_feedback_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    artifact_id uuid NOT NULL REFERENCES public.artifacts(id) ON DELETE CASCADE,
    artifact_version_id uuid NOT NULL REFERENCES public.artifact_versions(id) ON DELETE CASCADE,
    user_id uuid,
    rating smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment text,
    outcome text CHECK (outcome IN ('used', 'edited', 'discarded', 'won', 'lost')),
    quality_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_fingerprint text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_org_updated
    ON public.artifacts (organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_review_queue
    ON public.artifacts (organization_id, approval_status, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_versions_lookup
    ON public.artifact_versions (organization_id, artifact_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_evidence_lookup
    ON public.artifact_evidence_links (organization_id, artifact_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_feedback_outcome
    ON public.artifact_feedback_events (organization_id, outcome, created_at DESC);

ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifact_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifact_evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifact_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifact_feedback_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS artifacts_tenant_isolation ON public.artifacts;
CREATE POLICY artifacts_tenant_isolation ON public.artifacts
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS artifact_versions_tenant_isolation ON public.artifact_versions;
CREATE POLICY artifact_versions_tenant_isolation ON public.artifact_versions
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS artifact_evidence_links_tenant_isolation ON public.artifact_evidence_links;
CREATE POLICY artifact_evidence_links_tenant_isolation ON public.artifact_evidence_links
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS artifact_reviews_tenant_isolation ON public.artifact_reviews;
CREATE POLICY artifact_reviews_tenant_isolation ON public.artifact_reviews
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS artifact_feedback_events_tenant_isolation ON public.artifact_feedback_events;
CREATE POLICY artifact_feedback_events_tenant_isolation ON public.artifact_feedback_events
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
