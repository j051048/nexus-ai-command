-- Fix users table RLS self-referential recursion
-- The SELECT policy on users queries users itself, causing infinite recursion.
-- Replace with get_user_org_id() which is SECURITY DEFINER and queries organization_members.

-- 1. Fix users SELECT policy (was self-referencing)
DROP POLICY IF EXISTS "Users can view org members" ON public.users;
CREATE POLICY "Users can view org members" ON public.users
  FOR SELECT TO authenticated
  USING (
    organization_id = public.get_user_org_id(auth.uid())
    OR id = auth.uid()
  );

-- 2. Simplify users UPDATE policy (remove EXISTS subquery on users)
DROP POLICY IF EXISTS "User self update" ON public.users;
CREATE POLICY "User self update" ON public.users
  FOR UPDATE TO authenticated
  USING (id = auth.uid());

-- 3. Fix other tables that used subquery on users for org isolation
DROP POLICY IF EXISTS "Org Isolation for Sales Metrics" ON public.sales_metrics;
CREATE POLICY "Org Isolation for Sales Metrics" ON public.sales_metrics
  FOR ALL TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS "Org Isolation for Documents" ON public.documents;
CREATE POLICY "Org Isolation for Documents" ON public.documents
  FOR ALL TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

DROP POLICY IF EXISTS "Org Isolation for Approvals" ON public.approval_requests;
CREATE POLICY "Org Isolation for Approvals" ON public.approval_requests
  FOR ALL TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));
