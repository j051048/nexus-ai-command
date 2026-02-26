-- ============================================================================
-- Fix: Auth trigger must insert into public.users (not just profiles)
-- Root cause: Migration 20260126000002 changed handle_new_user() to only
--   write to profiles + user_roles, but the entire frontend reads from
--   public.users. New registrations became invisible.
-- ============================================================================

-- 0a. Ensure default organization exists
INSERT INTO public.organizations (id, name, slug)
VALUES ('00000000-0000-0000-0000-000000000000', 'Default Org', 'default-org')
ON CONFLICT (id) DO NOTHING;

-- 0b. Ensure organization_members table exists (may not have been created yet)
CREATE TABLE IF NOT EXISTS public.organization_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  role TEXT DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
  joined_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(organization_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_org_members_org ON public.organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON public.organization_members(user_id);

-- 1. Recreate handle_new_user() to write into ALL required tables
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role       public.user_role;
  _raw_role   text;
  _department text;
  _name       text;
  _default_org uuid := '00000000-0000-0000-0000-000000000000';
BEGIN
  _raw_role := NEW.raw_user_meta_data->>'role';
  _name     := COALESCE(NEW.raw_user_meta_data->>'name', NEW.email, 'New User');

  -- Map frontend role to user_role enum (founder/sales/employee/ai_assistant)
  IF _raw_role = 'boss' THEN
    _role := 'founder';
    _department := 'Management';
  ELSIF _raw_role = 'employee' THEN
    _role := 'sales';
    _department := 'Sales Dept';
  ELSE
    _role := 'sales';
    _department := 'Sales Dept';
  END IF;

  -- Use organization_id from metadata if provided, else default org
  IF (NEW.raw_user_meta_data->>'organization_id') IS NOT NULL THEN
    _default_org := (NEW.raw_user_meta_data->>'organization_id')::uuid;
  END IF;

  -- A) Insert into public.users (the table frontend actually reads)
  INSERT INTO public.users (id, name, role, department, organization_id, created_at, updated_at)
  VALUES (NEW.id, _name, _role, _department, _default_org, now(), now())
  ON CONFLICT (id) DO NOTHING;

  -- B) Insert into public.profiles (for new schema compatibility)
  INSERT INTO public.profiles (user_id, name, organization_id)
  VALUES (NEW.id, _name, _default_org)
  ON CONFLICT (user_id) DO NOTHING;

  -- C) Insert into public.user_roles (for RBAC compatibility)
  INSERT INTO public.user_roles (user_id, role)
  VALUES (
    NEW.id,
    CASE WHEN _raw_role = 'boss' THEN 'boss'::public.app_role
         ELSE 'employee'::public.app_role
    END
  )
  ON CONFLICT (user_id) DO NOTHING;

  -- D) Insert into organization_members (for org membership)
  INSERT INTO public.organization_members (organization_id, user_id, role)
  VALUES (_default_org, NEW.id, 'member')
  ON CONFLICT (organization_id, user_id) DO NOTHING;

  RETURN NEW;
EXCEPTION
  WHEN unique_violation THEN
    RETURN NEW;
  WHEN OTHERS THEN
    RAISE WARNING 'handle_new_user failed for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

-- 2. Drop the redundant org trigger (merged into handle_new_user above)
DROP TRIGGER IF EXISTS on_auth_user_created_org ON auth.users;

-- 3. Ensure the primary trigger exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4. Data fix: Backfill orphaned auth users who exist in auth.users
--    but NOT in public.users (e.g. afei_4806@qq.com)
INSERT INTO public.users (id, name, role, department, organization_id, created_at, updated_at)
SELECT
  au.id,
  COALESCE(au.raw_user_meta_data->>'name', au.email, 'Unknown'),
  CASE
    WHEN (au.raw_user_meta_data->>'role') = 'boss' THEN 'founder'::public.user_role
    ELSE 'sales'::public.user_role
  END,
  CASE
    WHEN (au.raw_user_meta_data->>'role') = 'boss' THEN 'Management'
    ELSE 'Sales Dept'
  END,
  '00000000-0000-0000-0000-000000000000',
  COALESCE(au.created_at, now()),
  now()
FROM auth.users au
LEFT JOIN public.users pu ON pu.id = au.id
WHERE pu.id IS NULL;

-- Also backfill organization_members for those users
INSERT INTO public.organization_members (organization_id, user_id, role)
SELECT
  '00000000-0000-0000-0000-000000000000',
  au.id,
  'member'
FROM auth.users au
LEFT JOIN public.organization_members om
  ON om.user_id = au.id
  AND om.organization_id = '00000000-0000-0000-0000-000000000000'
WHERE om.user_id IS NULL;

-- 5. Safety: Fix any existing users with NULL organization_id
UPDATE public.users
SET organization_id = '00000000-0000-0000-0000-000000000000'
WHERE organization_id IS NULL;
