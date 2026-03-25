-- Fix infinite recursion in organization_members RLS policy
-- Problem: "Org admins can manage members" policy queries organization_members
-- within its own RLS check, causing infinite recursion (error 42P17).
-- Solution: Use a SECURITY DEFINER helper function to bypass RLS when checking admin status.

-- 1. Create a SECURITY DEFINER helper to check if user is org admin/owner
CREATE OR REPLACE FUNCTION public.is_org_admin(_user_id UUID, _org_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.organization_members
    WHERE user_id = _user_id
      AND organization_id = _org_id
      AND role IN ('owner', 'admin')
  )
$$;

-- 2. Drop the recursive policy
DROP POLICY IF EXISTS "Org admins can manage members" ON public.organization_members;

-- 3. Recreate using the SECURITY DEFINER function (no recursion)
CREATE POLICY "Org admins can manage members"
  ON public.organization_members FOR ALL TO authenticated
  USING (
    public.is_org_admin(auth.uid(), organization_id)
  );
