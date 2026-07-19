-- Evidence-grounded solution workspace for scientific-instrument sales teams.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.solution_projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_code text NOT NULL,
    title text NOT NULL,
    customer_id uuid REFERENCES public.customers(id) ON DELETE SET NULL,
    customer_name text,
    industry text,
    region text,
    currency text NOT NULL DEFAULT 'CNY',
    budget_min numeric(18, 2),
    budget_max numeric(18, 2),
    instrument_line_code text REFERENCES public.instrument_line_catalog(code),
    application_scenario text,
    deadline timestamptz,
    status text NOT NULL DEFAULT 'discovery'
        CHECK (status IN ('discovery', 'drafting', 'review', 'approved', 'sent', 'won', 'lost', 'archived')),
    current_version integer NOT NULL DEFAULT 0,
    workspace jsonb NOT NULL DEFAULT '{}'::jsonb,
    outcome jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, project_code)
);

CREATE TABLE IF NOT EXISTS public.solution_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES public.solution_projects(id) ON DELETE CASCADE,
    version_number integer NOT NULL,
    title text NOT NULL,
    content jsonb NOT NULL,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    generation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_status text NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft', 'review', 'approved', 'rejected')),
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, version_number)
);

CREATE TABLE IF NOT EXISTS public.solution_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    name text NOT NULL,
    industry text,
    region text,
    instrument_line_code text REFERENCES public.instrument_line_catalog(code),
    structure jsonb NOT NULL,
    source_project_id uuid REFERENCES public.solution_projects(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'archived')),
    usage_count integer NOT NULL DEFAULT 0,
    success_count integer NOT NULL DEFAULT 0,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, name)
);

CREATE INDEX IF NOT EXISTS idx_solution_projects_org_status
    ON public.solution_projects (organization_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_projects_customer
    ON public.solution_projects (organization_id, customer_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_versions_project
    ON public.solution_versions (organization_id, project_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_solution_templates_scope
    ON public.solution_templates (organization_id, status, instrument_line_code);

ALTER TABLE public.solution_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS solution_projects_tenant_isolation ON public.solution_projects;
CREATE POLICY solution_projects_tenant_isolation ON public.solution_projects
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS solution_versions_tenant_isolation ON public.solution_versions;
CREATE POLICY solution_versions_tenant_isolation ON public.solution_versions
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS solution_templates_tenant_isolation ON public.solution_templates;
CREATE POLICY solution_templates_tenant_isolation ON public.solution_templates
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
