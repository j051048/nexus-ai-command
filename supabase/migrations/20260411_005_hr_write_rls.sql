-- Migration: Add HR write operation RLS policies
-- Date: 2026-04-11
-- Purpose: Enable INSERT/UPDATE for hr_employees, hr_performance_reviews, hr_candidates tables

-- 1. hr_employees: ensure table exists with RLS, add INSERT/UPDATE policies
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'hr_employees' AND table_schema = 'public') THEN
        CREATE TABLE public.hr_employees (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department TEXT,
            position TEXT,
            hire_date DATE,
            salary NUMERIC,
            status TEXT DEFAULT 'active',
            organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
            created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
            updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
    END IF;
END $$;

-- Ensure organization_id column exists
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_employees' AND column_name = 'organization_id') THEN
        ALTER TABLE public.hr_employees ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_hr_employees_org ON public.hr_employees(organization_id);
ALTER TABLE public.hr_employees ENABLE ROW LEVEL SECURITY;

-- SELECT policy (org isolation)
DROP POLICY IF EXISTS "Org Isolation for Employees" ON public.hr_employees;
CREATE POLICY "Org Isolation for Employees" ON public.hr_employees FOR SELECT TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);

-- INSERT policy (org members can insert)
DROP POLICY IF EXISTS "Org Insert for Employees" ON public.hr_employees;
CREATE POLICY "Org Insert for Employees" ON public.hr_employees FOR INSERT TO authenticated WITH CHECK (
    organization_id = public.get_user_org_id(auth.uid())
);

-- UPDATE policy (org members can update)
DROP POLICY IF EXISTS "Org Update for Employees" ON public.hr_employees;
CREATE POLICY "Org Update for Employees" ON public.hr_employees FOR UPDATE TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
) WITH CHECK (
    organization_id = public.get_user_org_id(auth.uid())
);


-- 2. hr_performance_reviews: add INSERT/UPDATE policies
ALTER TABLE public.hr_performance_reviews ENABLE ROW LEVEL SECURITY;

-- INSERT policy
DROP POLICY IF EXISTS "Org Insert for Performance Reviews" ON public.hr_performance_reviews;
CREATE POLICY "Org Insert for Performance Reviews" ON public.hr_performance_reviews FOR INSERT TO authenticated WITH CHECK (
    organization_id = public.get_user_org_id(auth.uid())
);

-- UPDATE policy
DROP POLICY IF EXISTS "Org Update for Performance Reviews" ON public.hr_performance_reviews;
CREATE POLICY "Org Update for Performance Reviews" ON public.hr_performance_reviews FOR UPDATE TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
) WITH CHECK (
    organization_id = public.get_user_org_id(auth.uid())
);


-- 3. hr_candidates: add INSERT/UPDATE policies
ALTER TABLE public.hr_candidates ENABLE ROW LEVEL SECURITY;

-- INSERT policy
DROP POLICY IF EXISTS "Org Insert for Candidates" ON public.hr_candidates;
CREATE POLICY "Org Insert for Candidates" ON public.hr_candidates FOR INSERT TO authenticated WITH CHECK (
    organization_id = public.get_user_org_id(auth.uid())
);

-- UPDATE policy
DROP POLICY IF EXISTS "Org Update for Candidates" ON public.hr_candidates;
CREATE POLICY "Org Update for Candidates" ON public.hr_candidates FOR UPDATE TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
) WITH CHECK (
    organization_id = public.get_user_org_id(auth.uid())
);
