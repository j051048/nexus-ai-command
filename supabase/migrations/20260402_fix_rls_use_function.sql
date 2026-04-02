-- Fix: Replace recursive RLS policies with get_user_org_id() function
-- The 20260402_add_rls_policies.sql used direct subquery on users table,
-- which causes infinite recursion when users table also has RLS.
-- This migration replaces all those policies with the correct pattern
-- using public.get_user_org_id(auth.uid()) SECURITY DEFINER function
-- (established in 20260222_fix_users_rls_recursion.sql).

-- ============================================================
-- 1. Drop all recursive policies from 20260402_add_rls_policies.sql
-- ============================================================

-- sales_leads
DROP POLICY IF EXISTS "租户隔离-查询" ON sales_leads;
DROP POLICY IF EXISTS "租户隔离-插入" ON sales_leads;
DROP POLICY IF EXISTS "租户隔离-更新" ON sales_leads;
DROP POLICY IF EXISTS "租户隔离-删除" ON sales_leads;

-- customers
DROP POLICY IF EXISTS "租户隔离-查询" ON customers;
DROP POLICY IF EXISTS "租户隔离-插入" ON customers;
DROP POLICY IF EXISTS "租户隔离-更新" ON customers;
DROP POLICY IF EXISTS "租户隔离-删除" ON customers;

-- contracts
DROP POLICY IF EXISTS "租户隔离-查询" ON contracts;
DROP POLICY IF EXISTS "租户隔离-插入" ON contracts;
DROP POLICY IF EXISTS "租户隔离-更新" ON contracts;
DROP POLICY IF EXISTS "租户隔离-删除" ON contracts;

-- work_orders
DROP POLICY IF EXISTS "租户隔离-查询" ON work_orders;
DROP POLICY IF EXISTS "租户隔离-插入" ON work_orders;
DROP POLICY IF EXISTS "租户隔离-更新" ON work_orders;
DROP POLICY IF EXISTS "租户隔离-删除" ON work_orders;

-- projects
DROP POLICY IF EXISTS "租户隔离-查询" ON projects;
DROP POLICY IF EXISTS "租户隔离-插入" ON projects;
DROP POLICY IF EXISTS "租户隔离-更新" ON projects;
DROP POLICY IF EXISTS "租户隔离-删除" ON projects;

-- approval_requests (also drop the one from 20260222 since we'll recreate)
DROP POLICY IF EXISTS "租户隔离-查询" ON approval_requests;
DROP POLICY IF EXISTS "租户隔离-插入" ON approval_requests;
DROP POLICY IF EXISTS "租户隔离-更新" ON approval_requests;
DROP POLICY IF EXISTS "租户隔离-删除" ON approval_requests;

-- ============================================================
-- 2. Recreate policies using get_user_org_id() (no recursion)
-- ============================================================

-- sales_leads
CREATE POLICY "org_isolation_select" ON sales_leads
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON sales_leads
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON sales_leads
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON sales_leads
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- customers
CREATE POLICY "org_isolation_select" ON customers
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON customers
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON customers
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON customers
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- contracts
CREATE POLICY "org_isolation_select" ON contracts
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON contracts
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON contracts
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON contracts
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- work_orders
CREATE POLICY "org_isolation_select" ON work_orders
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON work_orders
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON work_orders
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON work_orders
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- projects
CREATE POLICY "org_isolation_select" ON projects
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON projects
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON projects
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON projects
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- approval_requests
CREATE POLICY "org_isolation_select" ON approval_requests
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON approval_requests
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON approval_requests
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON approval_requests
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- ============================================================
-- 3. Add missing policies for tables that had RLS enabled but no policies
--    (assets, certificates, inventory, expenses were left with deny-all)
-- ============================================================

-- assets
DROP POLICY IF EXISTS "org_isolation_select" ON assets;
DROP POLICY IF EXISTS "org_isolation_insert" ON assets;
DROP POLICY IF EXISTS "org_isolation_update" ON assets;
DROP POLICY IF EXISTS "org_isolation_delete" ON assets;

CREATE POLICY "org_isolation_select" ON assets
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON assets
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON assets
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON assets
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- certificates
DROP POLICY IF EXISTS "org_isolation_select" ON certificates;
DROP POLICY IF EXISTS "org_isolation_insert" ON certificates;
DROP POLICY IF EXISTS "org_isolation_update" ON certificates;
DROP POLICY IF EXISTS "org_isolation_delete" ON certificates;

CREATE POLICY "org_isolation_select" ON certificates
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON certificates
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON certificates
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON certificates
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- inventory
DROP POLICY IF EXISTS "org_isolation_select" ON inventory;
DROP POLICY IF EXISTS "org_isolation_insert" ON inventory;
DROP POLICY IF EXISTS "org_isolation_update" ON inventory;
DROP POLICY IF EXISTS "org_isolation_delete" ON inventory;

CREATE POLICY "org_isolation_select" ON inventory
  FOR SELECT TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_insert" ON inventory
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_update" ON inventory
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_isolation_delete" ON inventory
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

-- NOTE: "expenses" table does not exist; the actual table is
-- finance_expense_details which cascades via approval_requests FK,
-- so no separate RLS policy is needed here.

-- ============================================================
-- 4. Re-enable RLS on organization_members with safe policy
--    Uses auth.uid() directly (no subquery on users table)
-- ============================================================

ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_members_select" ON organization_members;
DROP POLICY IF EXISTS "org_members_insert" ON organization_members;
DROP POLICY IF EXISTS "org_members_update" ON organization_members;
DROP POLICY IF EXISTS "org_members_delete" ON organization_members;

CREATE POLICY "org_members_select" ON organization_members
  FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_members_insert" ON organization_members
  FOR INSERT TO authenticated
  WITH CHECK (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_members_update" ON organization_members
  FOR UPDATE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));

CREATE POLICY "org_members_delete" ON organization_members
  FOR DELETE TO authenticated
  USING (organization_id = public.get_user_org_id(auth.uid()));
