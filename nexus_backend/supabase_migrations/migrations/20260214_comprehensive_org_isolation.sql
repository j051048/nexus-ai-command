-- Migration: 20260214_comprehensive_org_isolation
-- Purpose: Complete the organization isolation implementation by covering all remaining tables, creating missing ones, and standardizing on 'organization_id'.
-- 1. Create missing 'sales_targets' table
CREATE TABLE IF NOT EXISTS public.sales_targets (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id uuid REFERENCES public.organizations(id) NOT NULL,
    target_period text NOT NULL,
    -- 'YYYY-MM' or 'YYYY-Q#'
    target_type text NOT NULL CHECK (target_type IN ('monthly', 'quarterly')),
    revenue_target numeric DEFAULT 0,
    leads_target integer DEFAULT 0,
    conversions_target integer DEFAULT 0,
    win_rate_target numeric DEFAULT 0,
    created_by uuid REFERENCES auth.users(id),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(organization_id, target_period, target_type)
);
-- RLS for sales_targets
ALTER TABLE public.sales_targets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Sales Targets" ON public.sales_targets;
CREATE POLICY "Org Isolation for Sales Targets" ON public.sales_targets USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- 2. Migrate existing tables from 'org_id' to 'organization_id'
-- We handle specific tables known to use 'org_id' or missing isolation.
-- Helper block for migration logic
DO $$
DECLARE tbl text;
tables text [] := ARRAY ['projects', 'sales_leads', 'ai_settings', 'departments', 'notifications', 'document_embeddings', 'oa_tasks'];
BEGIN FOREACH tbl IN ARRAY tables LOOP -- Check if org_id exists
IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = tbl
        AND column_name = 'org_id'
) THEN -- Check if organization_id does NOT exist
IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = tbl
        AND column_name = 'organization_id'
) THEN -- Rename org_id to organization_id
EXECUTE format(
    'ALTER TABLE public.%I RENAME COLUMN org_id TO organization_id',
    tbl
);
ELSE -- both exist, copy data and drop org_id? 
-- Ideally we migrate data first
EXECUTE format(
    'UPDATE public.%I SET organization_id = org_id WHERE organization_id IS NULL',
    tbl
);
-- We won't drop org_id automatically here to prevent data loss if something is wrong, 
-- but in a clean migration we should. For now let's just ensure organization_id is populated.
END IF;
ELSE -- org_id doesn't exist. Check if organization_id exists.
IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = tbl
        AND column_name = 'organization_id'
) THEN -- Neither exists! Add organization_id
EXECUTE format(
    'ALTER TABLE public.%I ADD COLUMN organization_id uuid REFERENCES public.organizations(id)',
    tbl
);
END IF;
END IF;
-- Enforce FK if not exists (hard to check in DO block easily without elaborate query, skipping for now as explicit ALTER below is safer)
END LOOP;
END $$;
-- Explicitly add Constraints/FKs if they might be missing after rename (Rename retains constraints usually but let's be sure for new cols)
-- (Skipping redundant ALTERs if columns already have FKs from creation)
-- 3. Enforce RLS for migrated tables
-- Projects
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Projects" ON public.projects;
CREATE POLICY "Org Isolation for Projects" ON public.projects FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- Sales Leads
ALTER TABLE public.sales_leads ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Sales Leads" ON public.sales_leads;
CREATE POLICY "Org Isolation for Sales Leads" ON public.sales_leads FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- AI Settings
ALTER TABLE public.ai_settings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users can view own AI settings" ON public.ai_settings;
DROP POLICY IF EXISTS "Org Isolation for AI Settings" ON public.ai_settings;
CREATE POLICY "Org Isolation for AI Settings" ON public.ai_settings FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
    OR user_id = auth.uid()
);
-- Allow user to see their own settings regardless of org? Or strictly org?
-- Safest is (user_id = auth.uid()) for settings. Org might own them though. 
-- Let's stick to org isolation policy + user ownership.
-- Actually, if I change org, do I lose settings? Yes contextually.
-- Departments
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Departments" ON public.departments;
CREATE POLICY "Org Isolation for Departments" ON public.departments FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- Notifications
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Notifications" ON public.notifications;
CREATE POLICY "Org Isolation for Notifications" ON public.notifications FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
    AND user_id = auth.uid()
);
-- Document Embeddings (renamed org_id -> organization_id)
ALTER TABLE public.document_embeddings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Embeddings" ON public.document_embeddings;
CREATE POLICY "Org Isolation for Embeddings" ON public.document_embeddings FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- OA Tasks
ALTER TABLE public.oa_tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for OA Tasks" ON public.oa_tasks;
CREATE POLICY "Org Isolation for OA Tasks" ON public.oa_tasks FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- 4. Update match_documents RPC to use organization_id
-- We drop the old one(s) first to be clean.
DROP FUNCTION IF EXISTS match_documents(vector(1536), float, int, map, uuid);
DROP FUNCTION IF EXISTS match_documents(vector(1536), float, int, jsonb, uuid);
-- (Add other signatures if any, but let's just Replace/Create)
CREATE OR REPLACE FUNCTION match_documents(
        query_embedding vector(1536),
        match_threshold float,
        match_count int,
        filter jsonb DEFAULT '{}',
        p_org_id uuid DEFAULT NULL -- Use explicit parameter for org filtering
    ) RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        similarity float,
        organization_id uuid
    ) LANGUAGE plpgsql AS $$ BEGIN RETURN QUERY
SELECT document_embeddings.id,
    document_embeddings.content,
    document_embeddings.metadata,
    1 - (
        document_embeddings.embedding <=> query_embedding
    ) as similarity,
    document_embeddings.organization_id
FROM document_embeddings
WHERE 1 - (
        document_embeddings.embedding <=> query_embedding
    ) > match_threshold
    AND (
        p_org_id IS NULL
        OR document_embeddings.organization_id = p_org_id
    )
ORDER BY document_embeddings.embedding <=> query_embedding
LIMIT match_count;
END;
$$;