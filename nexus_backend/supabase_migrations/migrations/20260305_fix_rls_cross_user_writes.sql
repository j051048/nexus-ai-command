-- =====================================================================
-- Fix RLS policies for cross-user write operations
--
-- Problem: Several write operations (manager assignment, approval
-- delegation, performance scoring, task handover) were failing because
-- RLS policies only allowed self-modification. Code was bypassing RLS
-- with service-key client as a workaround.
--
-- Solution: Add SECURITY DEFINER helper functions and proper RLS
-- policies that allow authorized cross-user writes while keeping
-- org isolation intact.
-- =====================================================================

-- =========================================
-- 1. Helper functions (SECURITY DEFINER to avoid RLS recursion)
-- =========================================

-- Check if user has admin role (boss/founder)
-- Note: user_role enum values are: founder, sales, employee, manager, hr, boss, ai_assistant
CREATE OR REPLACE FUNCTION public.is_org_admin(_user_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users
    WHERE id = _user_id
      AND role IN ('boss', 'founder')
  );
$$;

-- Check if user has manager-or-above role
CREATE OR REPLACE FUNCTION public.is_manager_or_above(_user_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users
    WHERE id = _user_id
      AND role IN ('boss', 'founder', 'manager')
  );
$$;

-- =========================================
-- 2. users table - UPDATE policy
-- =========================================
-- Was: self-only (id = auth.uid())
-- Now: self OR manager+ in same org
-- Fixes: organization.py update_user_manager, hr_tools.py submit_rating

DROP POLICY IF EXISTS "User self update" ON public.users;
DROP POLICY IF EXISTS "User self or admin update" ON public.users;
DROP POLICY IF EXISTS "Manager can update team members" ON public.users;
DROP POLICY IF EXISTS "users_self_update" ON public.users;
DROP POLICY IF EXISTS "users_manager_update" ON public.users;

-- Self update (any user can update their own profile)
CREATE POLICY "users_self_update" ON public.users
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- Manager/admin cross-user update (for manager_id, score, etc.)
-- App logic controls which specific fields are updated.
CREATE POLICY "users_manager_update" ON public.users
  FOR UPDATE TO authenticated
  USING (
    public.get_user_org_id(auth.uid()) = organization_id
    AND public.is_manager_or_above(auth.uid())
  )
  WITH CHECK (
    public.get_user_org_id(auth.uid()) = organization_id
    AND public.is_manager_or_above(auth.uid())
  );

-- =========================================
-- 3. approval_requests table - UPDATE policy
-- =========================================
-- Was: has_role(auth.uid(), 'boss'::app_role) — broken because has_role
--      was changed to accept TEXT param, so 'boss'::app_role type mismatch.
--      Also, has_role checks user_roles table which may not have the role.
-- Now: is_org_admin() which checks users.role directly via SECURITY DEFINER.
-- Fixes: boss_tools.py SmartApprovalTool delegate

DROP POLICY IF EXISTS "Boss can update approvals" ON public.approval_requests;
DROP POLICY IF EXISTS "Approvers can update requests" ON public.approval_requests;
DROP POLICY IF EXISTS "approval_admin_update" ON public.approval_requests;
DROP POLICY IF EXISTS "approval_approver_update" ON public.approval_requests;

-- Boss/admin can update any approval in their org (approve, reject, delegate)
CREATE POLICY "approval_admin_update" ON public.approval_requests
  FOR UPDATE TO authenticated
  USING (
    public.get_user_org_id(auth.uid()) = organization_id
    AND public.is_org_admin(auth.uid())
  );

-- Submitter can update own pending approval (e.g. cancel/withdraw)
CREATE POLICY "approval_submitter_update" ON public.approval_requests
  FOR UPDATE TO authenticated
  USING (
    submitted_by = auth.uid()
    AND status = 'pending'
  );

-- =========================================
-- 4. oa_tasks table - fix org isolation
-- =========================================
-- Was: subquery SELECT FROM users (potential RLS recursion)
-- Now: get_user_org_id() with SECURITY DEFINER (safe)
-- Fixes: oa_tools.py WorkHandoverTool

ALTER TABLE IF EXISTS public.oa_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Org Isolation for OA Tasks" ON public.oa_tasks;
DROP POLICY IF EXISTS "oa_tasks_org_isolation" ON public.oa_tasks;

CREATE POLICY "oa_tasks_org_isolation" ON public.oa_tasks
  FOR ALL TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- =========================================
-- 5. performance_reviews table (if exists)
-- =========================================
-- Was: no RLS at all
-- Now: enable RLS + manager can insert, users can view own reviews
-- Fixes: hr_tools.py PerformanceReviewTool submit_rating

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'performance_reviews'
  ) THEN
    ALTER TABLE public.performance_reviews ENABLE ROW LEVEL SECURITY;

    EXECUTE 'DROP POLICY IF EXISTS "perf_review_insert" ON public.performance_reviews';
    EXECUTE 'CREATE POLICY "perf_review_insert" ON public.performance_reviews
      FOR INSERT TO authenticated
      WITH CHECK (
        reviewer_id = auth.uid()
        AND public.is_manager_or_above(auth.uid())
      )';

    EXECUTE 'DROP POLICY IF EXISTS "perf_review_select" ON public.performance_reviews';
    EXECUTE 'CREATE POLICY "perf_review_select" ON public.performance_reviews
      FOR SELECT TO authenticated
      USING (
        user_id = auth.uid()
        OR reviewer_id = auth.uid()
        OR public.is_manager_or_above(auth.uid())
      )';
  END IF;
END $$;
