-- ============================================================================
-- Fix: Auth trigger must insert into public.users (not just profiles)
-- Root cause: Migration 20260126000002 changed handle_new_user() to only
--   write to profiles + user_roles, but the entire frontend reads from
--   public.users. New registrations became invisible.
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

  -- Resolve organization: metadata > default org
  _org_id := (NEW.raw_user_meta_data->>'organization_id')::uuid;
  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations WHERE slug = 'default-org' LIMIT 1;
  END IF;
  -- Ultimate fallback: first org in table
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

-- 2. Drop redundant org trigger (merged above)
DROP TRIGGER IF EXISTS on_auth_user_created_org ON auth.users;

-- 3. Recreate primary trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4. Backfill orphaned auth users (e.g. afei_4806@qq.com)
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

-- Backfill organization_members
INSERT INTO public.organization_members (organization_id, user_id, role)
SELECT
  (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1),
  au.id,
  'member'
FROM auth.users au
LEFT JOIN public.organization_members om ON om.user_id = au.id
WHERE om.user_id IS NULL
  AND (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1) IS NOT NULL;

-- 5. Fix any users with NULL organization_id
UPDATE public.users
SET organization_id = (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
WHERE organization_id IS NULL
  AND (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1) IS NOT NULL;
