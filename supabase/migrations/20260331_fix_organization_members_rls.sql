-- Fix: Disable RLS on organization_members to prevent infinite recursion
-- Backend already handles tenant isolation via middleware and JWT

ALTER TABLE organization_members DISABLE ROW LEVEL SECURITY;

-- Drop any existing policies that cause recursion
DROP POLICY IF EXISTS organization_members_select_policy ON organization_members;
DROP POLICY IF EXISTS organization_members_insert_policy ON organization_members;
DROP POLICY IF EXISTS organization_members_update_policy ON organization_members;
DROP POLICY IF EXISTS organization_members_delete_policy ON organization_members;
