--P0 Security Fix: Enforce Organization Isolation
-- Add organization_id to core tables and enforce RLS policies
-- 1. Create Organization Table (if not exists, for referential integrity)
CREATE TABLE IF NOT EXISTS public.organizations (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name text NOT NULL,
    slug text,
    created_at timestamptz DEFAULT now()
);
-- Ensure slug column exists (for robustness)
DO $$ BEGIN IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'organizations'
        AND column_name = 'slug'
) THEN
ALTER TABLE public.organizations
ADD COLUMN slug text;
END IF;
END $$;
-- 2. Add organization_id to Users
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
-- Create a Default Organization for migration
DO $$ BEGIN IF NOT EXISTS (
    SELECT 1
    FROM public.organizations
    WHERE id = '00000000-0000-0000-0000-000000000000'
) THEN
INSERT INTO public.organizations (id, name, slug)
VALUES (
        '00000000-0000-0000-0000-000000000000',
        'Default Org',
        'default-org'
    );
END IF;
END $$;
-- Update existing users with Default Org if null
UPDATE public.users
SET organization_id = '00000000-0000-0000-0000-000000000000'
WHERE organization_id IS NULL;
-- Enforce NOT NULL (This is the critical fix)
ALTER TABLE public.users
ALTER COLUMN organization_id
SET NOT NULL;
-- 3. Add organization_id to Business Tables
-- Sales Metrics
ALTER TABLE public.sales_metrics
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
UPDATE public.sales_metrics sm
SET organization_id = u.organization_id
FROM public.users u
WHERE sm.user_id = u.id
    AND sm.organization_id IS NULL;
ALTER TABLE public.sales_metrics
ALTER COLUMN organization_id
SET NOT NULL;
-- Approval Requests
ALTER TABLE public.approval_requests
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
UPDATE public.approval_requests ar
SET organization_id = u.organization_id
FROM public.users u
WHERE ar.submitted_by = u.id
    AND ar.organization_id IS NULL;
ALTER TABLE public.approval_requests
ALTER COLUMN organization_id
SET NOT NULL;
-- Documents
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
UPDATE public.documents d
SET organization_id = u.organization_id
FROM public.users u
WHERE d.owner_id = u.id
    AND d.organization_id IS NULL;
-- 4. Update RLS Policies to Enforce Isolation
-- Users: Can see other users in SAME organization
DROP POLICY IF EXISTS "Users can view own data" ON public.users;
CREATE POLICY "Users can view org members" ON public.users FOR
SELECT USING (
        organization_id = (
            SELECT organization_id
            FROM public.users
            WHERE id = auth.uid()
        )
    );
-- Sales Metrics: Org Isolation
DROP POLICY IF EXISTS "Enable all for users" ON public.sales_metrics;
CREATE POLICY "Org Isolation for Sales Metrics" ON public.sales_metrics FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- Documents: Org Isolation
DROP POLICY IF EXISTS "Users can see own docs" ON public.documents;
CREATE POLICY "Org Isolation for Documents" ON public.documents FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- Approval Requests: Org Isolation
DROP POLICY IF EXISTS "Enable all for users" ON public.approval_requests;
CREATE POLICY "Org Isolation for Approvals" ON public.approval_requests FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- Fix Semantic Cache Policy (which was referencing organization_id)
-- Note: semantic_cache table had 'org_id text', we should migrate it to use UUID or match
-- Since it was just created, we can alter it.
-- Ensure semantic_cache exists (Idempotency)
CREATE TABLE IF NOT EXISTS public.semantic_cache (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    query_text text NOT NULL,
    response_text text NOT NULL,
    embedding vector(1536),
    user_id uuid REFERENCES auth.users(id),
    metadata jsonb DEFAULT '{}',
    hit_count int DEFAULT 1,
    last_hit_at timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now()
);
-- Safely handle org_id -> organization_id migration
DO $$ BEGIN -- Drop old org_id column if it exists
IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'semantic_cache'
        AND column_name = 'org_id'
) THEN
ALTER TABLE public.semantic_cache DROP COLUMN org_id;
END IF;
-- Add new organization_id column if it doesn't exist
IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'semantic_cache'
        AND column_name = 'organization_id'
) THEN
ALTER TABLE public.semantic_cache
ADD COLUMN organization_id uuid REFERENCES public.organizations(id);
END IF;
END $$;
-- Update Semantic Cache RLS
DROP POLICY IF EXISTS "semantic_cache_tenant_isolation" ON public.semantic_cache;
CREATE POLICY "semantic_cache_tenant_isolation" ON public.semantic_cache FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- 5. Audit Log Improvement
ALTER TABLE public.audit_logs
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
CREATE POLICY "Org Isolation for Audit Logs" ON public.audit_logs FOR
SELECT USING (
        organization_id = (
            SELECT organization_id
            FROM public.users
            WHERE id = auth.uid()
        )
    );