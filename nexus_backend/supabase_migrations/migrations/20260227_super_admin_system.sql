-- ============================================================================
-- Feature: Super Admin System + Boss Registration Approval
--
-- 1. Adds pending_boss, super_admin to app_role enum
-- 2. Creates is_super_admin() check function
-- 3. Updates get_user_role() to detect pending_boss
-- 4. Updates handle_new_user() trigger: boss → pending_boss
-- 5. Sets j051048@gmail.com as super_admin
-- 6. Admin RPC functions: approve/reject boss, list pending, delete org
-- ============================================================================

-- 1. Add new enum values
-- Note: Supabase may store the type without schema prefix. Try without 'public.' first.
ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'pending_boss';
ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'super_admin';

-- 2. is_super_admin() — checks user_roles table
CREATE OR REPLACE FUNCTION public.is_super_admin(_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql SECURITY DEFINER STABLE
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = _user_id AND role = 'super_admin'
  );
$$;

-- 3. Update get_user_role() — detect pending_boss from user_roles
CREATE OR REPLACE FUNCTION public.get_user_role(_user_id UUID)
RETURNS TEXT AS $$
DECLARE
  _role user_role;
  _has_pending BOOLEAN;
BEGIN
  -- Check for pending boss in user_roles
  SELECT EXISTS(
    SELECT 1 FROM public.user_roles
    WHERE user_id = _user_id AND role = 'pending_boss'
  ) INTO _has_pending;
  IF _has_pending THEN RETURN 'pending_boss'; END IF;

  -- Normal role from users table
  SELECT role INTO _role FROM public.users WHERE id = _user_id;
  IF _role IS NULL THEN RETURN 'employee';
  ELSIF _role = 'founder' THEN RETURN 'boss';
  ELSIF _role = 'boss' THEN RETURN 'boss';
  ELSIF _role = 'manager' THEN RETURN 'manager';
  ELSIF _role = 'ai_assistant' THEN RETURN 'ai_assistant';
  ELSE RETURN 'employee';
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. Update handle_new_user() — boss registration → pending_boss
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role       user_role;
  _app_role   app_role;
  _raw_role   text;
  _department text;
  _name       text;
  _org_id     uuid;
  _invite     text;
BEGIN
  _raw_role := NEW.raw_user_meta_data->>'role';
  _name     := COALESCE(NEW.raw_user_meta_data->>'name', NEW.email, 'New User');

  -- Boss registration: start as sales (employee-level), pending approval
  -- Employee registration: normal sales role
  IF _raw_role = 'boss' THEN
    _role := 'sales';           -- No boss privileges until approved
    _department := 'Management';
    _app_role := 'pending_boss'; -- Pending super admin approval
  ELSE
    _role := 'sales';
    _department := 'Sales Dept';
    _app_role := 'employee';
  END IF;

  -- Resolve organization:
  --   1. Explicit organization_id from metadata
  --   2. Invite code validation
  --   3. Fallback to default org
  _org_id := (NEW.raw_user_meta_data->>'organization_id')::uuid;

  IF _org_id IS NULL THEN
    _invite := NEW.raw_user_meta_data->>'invite_code';
    IF _invite IS NOT NULL AND _invite != '' THEN
      SELECT id INTO _org_id
      FROM public.organizations
      WHERE invite_code = _invite
        AND invite_code_enabled = true
        AND (invite_code_expires_at IS NULL OR invite_code_expires_at > now());
    END IF;
  END IF;

  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations WHERE slug = 'default-org' LIMIT 1;
  END IF;
  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations LIMIT 1;
  END IF;

  -- A) public.users
  INSERT INTO public.users (id, name, role, department, organization_id, created_at, updated_at)
  VALUES (NEW.id, _name, _role, _department, _org_id, now(), now())
  ON CONFLICT (id) DO NOTHING;

  -- B) public.profiles
  INSERT INTO public.profiles (user_id, name, organization_id)
  VALUES (NEW.id, _name, _org_id)
  ON CONFLICT (user_id) DO NOTHING;

  -- C) public.user_roles — uses pending_boss for boss registrations
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, _app_role)
  ON CONFLICT DO NOTHING;

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

-- 5. Set j051048@gmail.com as super_admin (keep existing roles)
INSERT INTO public.user_roles (user_id, role)
SELECT au.id, 'super_admin'::app_role
FROM auth.users au
WHERE au.email = 'j051048@gmail.com'
ON CONFLICT DO NOTHING;

-- 6. Admin RPC: List pending boss approvals
CREATE OR REPLACE FUNCTION public.admin_list_pending_bosses()
RETURNS TABLE(
  user_id UUID,
  name TEXT,
  email TEXT,
  created_at TIMESTAMPTZ,
  organization_name TEXT
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  RETURN QUERY
  SELECT
    u.id AS user_id,
    u.name::TEXT,
    au.email::TEXT,
    au.created_at,
    COALESCE(o.name, 'N/A')::TEXT AS organization_name
  FROM public.user_roles ur
  JOIN public.users u ON u.id = ur.user_id
  JOIN auth.users au ON au.id = ur.user_id
  LEFT JOIN public.organizations o ON o.id = u.organization_id
  WHERE ur.role = 'pending_boss'
  ORDER BY au.created_at DESC;
END;
$$;

-- 7. Admin RPC: Approve boss
CREATE OR REPLACE FUNCTION public.admin_approve_boss(_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  -- Upgrade users.role to founder
  UPDATE public.users
  SET role = 'founder', department = 'Management', updated_at = now()
  WHERE id = _user_id;

  -- Change user_roles from pending_boss to boss
  UPDATE public.user_roles
  SET role = 'boss'
  WHERE user_id = _user_id AND role = 'pending_boss';
END;
$$;

-- 8. Admin RPC: Reject boss (keep as employee)
CREATE OR REPLACE FUNCTION public.admin_reject_boss(_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  -- Change pending_boss to employee
  UPDATE public.user_roles
  SET role = 'employee'
  WHERE user_id = _user_id AND role = 'pending_boss';
END;
$$;

-- 9. Admin RPC: List all organizations with member counts
CREATE OR REPLACE FUNCTION public.admin_list_organizations()
RETURNS TABLE(
  org_id UUID,
  name TEXT,
  slug TEXT,
  member_count BIGINT,
  created_at TIMESTAMPTZ
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  RETURN QUERY
  SELECT
    o.id AS org_id,
    o.name::TEXT,
    o.slug::TEXT,
    COUNT(u.id) AS member_count,
    o.created_at
  FROM public.organizations o
  LEFT JOIN public.users u ON u.organization_id = o.id
  GROUP BY o.id, o.name, o.slug, o.created_at
  ORDER BY o.created_at DESC;
END;
$$;

-- 10. Admin RPC: Delete organization and all its data
CREATE OR REPLACE FUNCTION public.admin_delete_organization(_org_id UUID)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _slug TEXT;
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  SELECT slug INTO _slug FROM public.organizations WHERE id = _org_id;
  IF _slug = 'default-org' THEN
    RAISE EXCEPTION 'Cannot delete the default organization';
  END IF;

  -- Move users to default org before deleting
  UPDATE public.users
  SET organization_id = (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
  WHERE organization_id = _org_id;

  UPDATE public.profiles
  SET organization_id = (SELECT id FROM public.organizations WHERE slug = 'default-org' LIMIT 1)
  WHERE organization_id = _org_id;

  -- Delete organization_members
  DELETE FROM public.organization_members WHERE organization_id = _org_id;

  -- Delete the organization
  DELETE FROM public.organizations WHERE id = _org_id;
END;
$$;
