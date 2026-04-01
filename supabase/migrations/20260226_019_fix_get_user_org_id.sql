-- ============================================================================
-- Migration: Fix get_user_org_id() missing SECURITY DEFINER
-- Date: 2026-02-26
-- Purpose: The current get_user_org_id(p_user_id) function queries public.users
--          but lacks SECURITY DEFINER. When called from users table RLS policy,
--          this causes infinite recursion:
--            users RLS → get_user_org_id() → SELECT from users → users RLS → ...
--          Adding SECURITY DEFINER makes the function bypass RLS, breaking the loop.
-- ============================================================================
-- Use CREATE OR REPLACE (cannot DROP because 6 RLS policies depend on it)
CREATE OR REPLACE FUNCTION public.get_user_org_id(p_user_id uuid) RETURNS uuid LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = public AS $$
DECLARE v_org_id uuid;
BEGIN
SELECT organization_id INTO v_org_id
FROM public.users
WHERE id = p_user_id;
RETURN v_org_id;
END;
$$;