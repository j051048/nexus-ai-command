-- Operational depth for the scientific-instrument solution workspace.
-- The migration is intentionally additive and idempotent: existing projects
-- and historical documents remain readable while new workflows are enabled.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Converge the document tenant/index contract on `organization_id`. Older
-- installations may still carry an `org_id` column from an early migration.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'org_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'organization_id'
    ) THEN
        ALTER TABLE public.documents RENAME COLUMN org_id TO organization_id;
    ELSIF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'org_id'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'organization_id'
    ) THEN
        UPDATE public.documents
        SET organization_id = COALESCE(organization_id, org_id)
        WHERE organization_id IS NULL AND org_id IS NOT NULL;
    END IF;
END $$;

DROP INDEX IF EXISTS public.idx_documents_org_id;
CREATE INDEX IF NOT EXISTS idx_documents_organization_id
    ON public.documents (organization_id, created_at DESC);

UPDATE public.documents
SET source_version = COALESCE(NULLIF(source_version, ''), 'v1'),
    review_status = CASE
        WHEN review_status IS NOT NULL AND review_status <> '' THEN review_status
        WHEN status IN ('ready', 'completed') THEN 'verified'
        ELSE 'pending'
    END,
    indexed_at = COALESCE(indexed_at, created_at)
WHERE source_version IS NULL
   OR source_version = ''
   OR review_status IS NULL
   OR review_status = ''
   OR indexed_at IS NULL;

ALTER TABLE public.solution_projects
    ADD COLUMN IF NOT EXISTS generation_fingerprint text,
    ADD COLUMN IF NOT EXISTS quality_evaluation jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS bid_readiness jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.solution_price_books (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    name text NOT NULL,
    region text,
    currency text NOT NULL DEFAULT 'CNY',
    tax_rate numeric(7, 4) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 1),
    is_default boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'archived')),
    valid_from timestamptz,
    valid_until timestamptz,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, name)
);

CREATE TABLE IF NOT EXISTS public.solution_price_book_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    price_book_id uuid NOT NULL REFERENCES public.solution_price_books(id) ON DELETE CASCADE,
    product_id uuid NOT NULL REFERENCES public.instrument_product_catalog(id) ON DELETE CASCADE,
    unit_price numeric(18, 2) NOT NULL CHECK (unit_price >= 0),
    floor_price numeric(18, 2) CHECK (floor_price IS NULL OR floor_price >= 0),
    max_discount_percent numeric(7, 3) NOT NULL DEFAULT 0
        CHECK (max_discount_percent BETWEEN 0 AND 100),
    minimum_margin_percent numeric(7, 3)
        CHECK (minimum_margin_percent IS NULL OR minimum_margin_percent BETWEEN -100 AND 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (price_book_id, product_id)
);

CREATE TABLE IF NOT EXISTS public.solution_commercial_approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES public.solution_projects(id) ON DELETE CASCADE,
    package_id text NOT NULL,
    quote_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    requested_by uuid,
    decided_by uuid,
    decision_note text,
    requested_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.solution_review_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES public.solution_projects(id) ON DELETE CASCADE,
    version_number integer,
    section_id text NOT NULL,
    content text NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_by uuid,
    resolved_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);

CREATE TABLE IF NOT EXISTS public.solution_quality_eval_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES public.solution_projects(id) ON DELETE CASCADE,
    version_number integer,
    evaluator_version text NOT NULL,
    score numeric(7, 3) NOT NULL CHECK (score BETWEEN 0 AND 100),
    dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
    findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.solution_delivery_events
    ADD COLUMN IF NOT EXISTS request_key text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_solution_delivery_request_key
    ON public.solution_delivery_events (organization_id, request_key)
    WHERE request_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_solution_price_books_scope
    ON public.solution_price_books (organization_id, status, region, is_default DESC);
CREATE INDEX IF NOT EXISTS idx_solution_price_book_items_lookup
    ON public.solution_price_book_items (organization_id, price_book_id, product_id);
CREATE INDEX IF NOT EXISTS idx_solution_commercial_approval_queue
    ON public.solution_commercial_approvals (organization_id, status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_review_comments_project
    ON public.solution_review_comments (organization_id, project_id, section_id, status);
CREATE INDEX IF NOT EXISTS idx_solution_quality_eval_project
    ON public.solution_quality_eval_runs (organization_id, project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_solution_projects_generation_fingerprint
    ON public.solution_projects (organization_id, generation_fingerprint)
    WHERE generation_fingerprint IS NOT NULL;

ALTER TABLE public.solution_price_books ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_price_book_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_commercial_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_review_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.solution_quality_eval_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS solution_price_books_tenant_isolation ON public.solution_price_books;
CREATE POLICY solution_price_books_tenant_isolation ON public.solution_price_books
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS solution_price_book_items_tenant_isolation ON public.solution_price_book_items;
CREATE POLICY solution_price_book_items_tenant_isolation ON public.solution_price_book_items
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS solution_commercial_approvals_tenant_isolation ON public.solution_commercial_approvals;
CREATE POLICY solution_commercial_approvals_tenant_isolation ON public.solution_commercial_approvals
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS solution_review_comments_tenant_isolation ON public.solution_review_comments;
CREATE POLICY solution_review_comments_tenant_isolation ON public.solution_review_comments
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS solution_quality_eval_runs_tenant_isolation ON public.solution_quality_eval_runs;
CREATE POLICY solution_quality_eval_runs_tenant_isolation ON public.solution_quality_eval_runs
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
