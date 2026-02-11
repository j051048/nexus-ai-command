-- Migration: 20260214_fix_finance_invoices_isolation.sql
-- Purpose: Standardize 'finance_invoices' on 'organization_id' and apply RLS.
-- 1. Rename org_id to organization_id if needed
DO $$ BEGIN IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'finance_invoices'
        AND column_name = 'org_id'
)
AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'finance_invoices'
        AND column_name = 'organization_id'
) THEN
ALTER TABLE public.finance_invoices
    RENAME COLUMN org_id TO organization_id;
ELSIF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'finance_invoices'
        AND column_name = 'organization_id'
) THEN
ALTER TABLE public.finance_invoices
ADD COLUMN organization_id uuid REFERENCES public.organizations(id);
END IF;
-- If both exist, keep organization_id and maybe merge (simplified check)
END $$;
-- 2. Enforce RLS
ALTER TABLE public.finance_invoices ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Invoices" ON public.finance_invoices;
CREATE POLICY "Org Isolation for Invoices" ON public.finance_invoices FOR ALL USING (
    organization_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- Also check finance_budgets (implicitly isolated via project_id/department, but RLS on table is good strictly speaking)
-- For now, finance_invoices was explicit vulnerability due to org_id column presence.