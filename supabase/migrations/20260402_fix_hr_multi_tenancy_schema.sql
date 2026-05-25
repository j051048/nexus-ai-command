-- Migration: Add consistent organization_id to HR tables
-- Date: 2026-04-02
-- Purpose: Fix 500 errors in HR module due to missing organization_id columns.

-- 1. hr_attendance
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_attendance' AND column_name = 'organization_id') THEN
        ALTER TABLE public.hr_attendance ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_hr_attendance_org ON public.hr_attendance(organization_id);
ALTER TABLE public.hr_attendance ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Attendance" ON public.hr_attendance;
CREATE POLICY "Org Isolation for Attendance" ON public.hr_attendance FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);

-- 2. hr_job_positions
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_job_positions' AND column_name = 'organization_id') THEN
        ALTER TABLE public.hr_job_positions ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_hr_job_positions_org ON public.hr_job_positions(organization_id);
ALTER TABLE public.hr_job_positions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Job Positions" ON public.hr_job_positions;
CREATE POLICY "Org Isolation for Job Positions" ON public.hr_job_positions FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);

-- 3. hr_candidates
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_candidates' AND column_name = 'organization_id') THEN
        ALTER TABLE public.hr_candidates ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_hr_candidates_org ON public.hr_candidates(organization_id);
ALTER TABLE public.hr_candidates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Candidates" ON public.hr_candidates;
CREATE POLICY "Org Isolation for Candidates" ON public.hr_candidates FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);

-- 4. hr_salary_records (adding organization_id for consistency)
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_salary_records' AND column_name = 'organization_id') THEN
        ALTER TABLE public.hr_salary_records ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_salary_records' AND column_name = 'org_id') THEN
        UPDATE public.hr_salary_records
        SET organization_id = org_id
        WHERE organization_id IS NULL AND org_id IS NOT NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_hr_salary_org ON public.hr_salary_records(organization_id);
DROP POLICY IF EXISTS "Org Isolation for Salary Records" ON public.hr_salary_records;
CREATE POLICY "Org Isolation for Salary Records" ON public.hr_salary_records FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);

-- 5. hr_performance_reviews (adding organization_id for consistency)
DO $$ BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_performance_reviews' AND column_name = 'organization_id') THEN
        ALTER TABLE public.hr_performance_reviews ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'hr_performance_reviews' AND column_name = 'org_id') THEN
        UPDATE public.hr_performance_reviews
        SET organization_id = org_id
        WHERE organization_id IS NULL AND org_id IS NOT NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_hr_performance_org ON public.hr_performance_reviews(organization_id);
DROP POLICY IF EXISTS "Org Isolation for Performance" ON public.hr_performance_reviews;
CREATE POLICY "Org Isolation for Performance" ON public.hr_performance_reviews FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);
