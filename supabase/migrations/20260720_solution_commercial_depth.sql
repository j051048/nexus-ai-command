-- Commercial, evidence and delivery contracts for the scientific-instrument
-- solution workspace. This migration is additive so existing workspaces remain
-- readable while the v1 client progressively adopts the new fields.

ALTER TABLE public.instrument_product_catalog
    ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'CNY',
    ADD COLUMN IF NOT EXISTS list_price numeric(18, 2),
    ADD COLUMN IF NOT EXISTS standard_cost numeric(18, 2),
    ADD COLUMN IF NOT EXISTS lead_time_days integer,
    ADD COLUMN IF NOT EXISTS warranty_months integer,
    ADD COLUMN IF NOT EXISTS lifecycle_status text NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS validation_status text NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS configuration_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS compatibility_rules jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS service_items jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS consumables jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS reviewed_by uuid,
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'instrument_product_catalog_lifecycle_status_check'
    ) THEN
        ALTER TABLE public.instrument_product_catalog
            ADD CONSTRAINT instrument_product_catalog_lifecycle_status_check
            CHECK (lifecycle_status IN ('draft', 'active', 'limited', 'eol'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'instrument_product_catalog_validation_status_check'
    ) THEN
        ALTER TABLE public.instrument_product_catalog
            ADD CONSTRAINT instrument_product_catalog_validation_status_check
            CHECK (validation_status IN ('draft', 'verified', 'rejected'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'instrument_product_catalog_price_check'
    ) THEN
        ALTER TABLE public.instrument_product_catalog
            ADD CONSTRAINT instrument_product_catalog_price_check
            CHECK (
                (list_price IS NULL OR list_price >= 0)
                AND (standard_cost IS NULL OR standard_cost >= 0)
                AND (lead_time_days IS NULL OR lead_time_days >= 0)
                AND (warranty_months IS NULL OR warranty_months >= 0)
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_instrument_products_validation
    ON public.instrument_product_catalog
    (organization_id, validation_status, lifecycle_status, updated_at DESC);

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS source_version text,
    ADD COLUMN IF NOT EXISTS valid_until timestamptz,
    ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS reviewed_by uuid,
    ADD COLUMN IF NOT EXISTS reviewed_at timestamptz,
    ADD COLUMN IF NOT EXISTS indexed_at timestamptz,
    ADD COLUMN IF NOT EXISTS quality_score numeric(5, 4);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'documents_review_status_check'
    ) THEN
        ALTER TABLE public.documents
            ADD CONSTRAINT documents_review_status_check
            CHECK (review_status IN ('pending', 'verified', 'rejected', 'expired'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'documents_quality_score_check'
    ) THEN
        ALTER TABLE public.documents
            ADD CONSTRAINT documents_quality_score_check
            CHECK (quality_score IS NULL OR quality_score BETWEEN 0 AND 1);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_knowledge_governance
    ON public.documents
    (organization_id, review_status, doc_type, valid_until, created_at DESC);

ALTER TABLE public.solution_projects
    ADD COLUMN IF NOT EXISTS source_document_ids uuid[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS linked_tender_project_id bigint;

ALTER TABLE public.bid_project
    ADD COLUMN IF NOT EXISTS source_solution_project_id uuid
        REFERENCES public.solution_projects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_solution_projects_linked_tender
    ON public.solution_projects (organization_id, linked_tender_project_id);
CREATE INDEX IF NOT EXISTS idx_bid_project_source_solution
    ON public.bid_project (tenant_id, source_solution_project_id);

CREATE TABLE IF NOT EXISTS public.solution_feedback_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES public.solution_projects(id) ON DELETE CASCADE,
    version_number integer,
    section_id text,
    rating smallint CHECK (rating BETWEEN 1 AND 5),
    change_type text CHECK (
        change_type IN ('accepted', 'edited', 'rejected', 'won', 'lost', 'other')
    ),
    note text,
    original_content text,
    revised_content text,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.solution_delivery_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES public.solution_projects(id) ON DELETE CASCADE,
    version_number integer,
    channel text NOT NULL,
    status text NOT NULL DEFAULT 'prepared'
        CHECK (status IN ('prepared', 'sent', 'acknowledged', 'failed')),
    artifact_name text,
    artifact_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.enterprise_connector_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    connector_code text NOT NULL,
    display_name text NOT NULL,
    connector_type text NOT NULL
        CHECK (connector_type IN ('crm', 'erp', 'im', 'storage', 'email', 'custom')),
    status text NOT NULL DEFAULT 'disabled'
        CHECK (status IN ('disabled', 'active', 'error')),
    capabilities jsonb NOT NULL DEFAULT '[]'::jsonb,
    config_ref text,
    last_health_at timestamptz,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, connector_code)
);

CREATE INDEX IF NOT EXISTS idx_solution_feedback_project
    ON public.solution_feedback_events
    (organization_id, project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_delivery_project
    ON public.solution_delivery_events
    (organization_id, project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_connector_registry_org_status
    ON public.enterprise_connector_registry
    (organization_id, status, connector_type);

ALTER TABLE public.solution_feedback_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_delivery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enterprise_connector_registry ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS solution_feedback_events_tenant_isolation
    ON public.solution_feedback_events;
CREATE POLICY solution_feedback_events_tenant_isolation
    ON public.solution_feedback_events
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS solution_delivery_events_tenant_isolation
    ON public.solution_delivery_events;
CREATE POLICY solution_delivery_events_tenant_isolation
    ON public.solution_delivery_events
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS enterprise_connector_registry_tenant_isolation
    ON public.enterprise_connector_registry;
CREATE POLICY enterprise_connector_registry_tenant_isolation
    ON public.enterprise_connector_registry
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
