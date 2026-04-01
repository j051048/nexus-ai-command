-- ============================================================================
-- Migration: Add organization_id to missed tables (oa_meeting_bookings, finance_budgets)
-- Date: 2026-02-26
-- Purpose: These tables were not updated during the initial multi-tenant migration,
--          causing errors in OA Center and Finance Center when querying.
-- ============================================================================
-- 1. oa_meeting_bookings
DO $$ BEGIN IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_name = 'oa_meeting_bookings'
        AND table_schema = 'public'
) THEN
ALTER TABLE public.oa_meeting_bookings
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE
SET NULL;
END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_meeting_bookings_org ON public.oa_meeting_bookings(organization_id);
ALTER TABLE public.oa_meeting_bookings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Meeting Bookings" ON public.oa_meeting_bookings;
CREATE POLICY "Org Isolation for Meeting Bookings" ON public.oa_meeting_bookings FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);
-- 2. finance_budgets
DO $$ BEGIN IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_name = 'finance_budgets'
        AND table_schema = 'public'
) THEN
ALTER TABLE public.finance_budgets
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE
SET NULL;
END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_finance_budgets_org ON public.finance_budgets(organization_id);
ALTER TABLE public.finance_budgets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Org Isolation for Budgets" ON public.finance_budgets;
CREATE POLICY "Org Isolation for Budgets" ON public.finance_budgets FOR ALL TO authenticated USING (
    organization_id = public.get_user_org_id(auth.uid())
);