-- ============================================================================
-- Fix: Auth trigger must insert into public.users (not just profiles)
-- + Force ALL users into the main organization (slug='default-org')
-- + Clean up auto-generated personal orgs ("XX 的企业")
-- ============================================================================

-- 0a. Ensure a default organization exists (reuse existing if slug taken)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.organizations WHERE slug = 'default-org') THEN
    INSERT INTO public.organizations (id, name, slug)
    VALUES (gen_random_uuid(), 'Default Org', 'default-org');
  END IF;
END $$;

-- 0b. Ensure organization_members table exists
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

-- 1. Recreate handle_new_user() — dynamically looks up default org
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role       public.user_role;
  _raw_role   text;
  _department text;
  _name       text;
  _org_id     uuid;
BEGIN
  _raw_role := NEW.raw_user_meta_data->>'role';
  _name     := COALESCE(NEW.raw_user_meta_data->>'name', NEW.email, 'New User');

  -- Map frontend role to user_role enum
  IF _raw_role = 'boss' THEN
    _role := 'founder';
    _department := 'Management';
  ELSE
    _role := 'sales';
    _department := 'Sales Dept';
  END IF;

  -- Resolve organization: metadata > default org > first org
  _org_id := (NEW.raw_user_meta_data->>'organization_id')::uuid;
  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations WHERE slug = 'default-org' LIMIT 1;
  END IF;
  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations LIMIT 1;
  END IF;

  -- A) public.users (the table frontend reads)
  INSERT INTO public.users (id, name, role, department, organization_id, created_at, updated_at)
  VALUES (NEW.id, _name, _role, _department, _org_id, now(), now())
  ON CONFLICT (id) DO NOTHING;

  -- B) public.profiles (new schema compat)
  INSERT INTO public.profiles (user_id, name, organization_id)
  VALUES (NEW.id, _name, _org_id)
  ON CONFLICT (user_id) DO NOTHING;

  -- C) public.user_roles (RBAC compat)
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, CASE WHEN _raw_role = 'boss' THEN 'boss'::public.app_role ELSE 'employee'::public.app_role END)
  ON CONFLICT (user_id) DO NOTHING;

  -- D) organization_members
  IF _org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (_org_id, NEW.id, 'member')
    ON CONFLICT (organization_id, user_id) DO NOTHING;
  END IF;

  RETURN NEW;
EXCEPTION
  WHEN unique_violation THEN RETURN NEW;
  WHEN OTHERS THEN
    RAISE WARNING 'handle_new_user failed for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

-- 2. Drop ALL auth.users triggers, then recreate only the correct one
--    This kills any hidden trigger that auto-creates personal orgs
DROP TRIGGER IF EXISTS on_auth_user_created_org ON auth.users;
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS handle_new_user_trigger ON auth.users;
DROP TRIGGER IF EXISTS create_user_on_signup ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Also drop the handle_new_user_org function to prevent any resurrection
DROP FUNCTION IF EXISTS public.handle_new_user_org() CASCADE;

-- 3. Backfill: insert orphaned auth users into public.users
INSERT INTO public.users (id, name, role, department, organization_id, created_at, updated_at)
SELECT
  au.id,
  COALESCE(au.raw_user_meta_data->>'name', au.email, 'Unknown'),
  CASE WHEN (au.raw_user_meta_data->>'role') = 'boss' THEN 'founder'::public.user_role
       ELSE 'sales'::public.user_role END,
  CASE WHEN (au.raw_user_meta_data->>'role') = 'boss' THEN 'Management'
       ELSE 'Sales Dept' END,
  (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1),
  COALESCE(au.created_at, now()),
  now()
FROM auth.users au
LEFT JOIN public.users pu ON pu.id = au.id
WHERE pu.id IS NULL;

-- 4. KEY FIX: Force ALL users into the main org (default-org)
--    This fixes users who got placed in auto-generated personal orgs
UPDATE public.users
SET organization_id = (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
WHERE organization_id != (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
   OR organization_id IS NULL;

-- Also sync profiles table
UPDATE public.profiles
SET organization_id = (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
WHERE organization_id IS DISTINCT FROM (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1);

-- 5. Ensure all users are in organization_members for the main org
INSERT INTO public.organization_members (organization_id, user_id, role)
SELECT
  (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1),
  u.id,
  'member'
FROM public.users u
WHERE NOT EXISTS (
  SELECT 1 FROM public.organization_members om
  WHERE om.user_id = u.id
    AND om.organization_id = (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
)
AND (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1) IS NOT NULL;

-- 6. Clean up auto-generated personal orgs (like "文池 的企业", "Test User 的企业")
--    Delete orgs that are NOT the main org and have no users left
DELETE FROM public.organizations
WHERE slug != 'default-org'
  AND id NOT IN (SELECT DISTINCT organization_id FROM public.users WHERE organization_id IS NOT NULL);

-- 7. List all triggers on auth.users for diagnostic (check Supabase logs)
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT tgname, tgfoid::regproc AS func_name
    FROM pg_trigger
    WHERE tgrelid = 'auth.users'::regclass
  LOOP
    RAISE NOTICE 'Trigger on auth.users: % -> %', r.tgname, r.func_name;
  END LOOP;
END $$;
