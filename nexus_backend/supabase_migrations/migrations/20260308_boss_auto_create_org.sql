-- ============================================================================
-- Feature: Boss Registration Auto-Creates New Organization
--
-- Previously, boss registration fell back to default-org because no
-- invite_code or organization_id was provided. Now bosses automatically
-- get a new organization ("XX 的企业") created for them.
--
-- Changes:
--   1. handle_new_user() — boss path creates new org instead of fallback
--   2. admin_approve_boss() — ensures boss is org owner after approval
--   3. admin_reject_boss() — migrates rejected boss to default-org, cleans up empty org
-- ============================================================================

-- 1. Rewrite handle_new_user() with boss auto-create org logic
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role       user_role;
  _raw_role   text;
  _department text;
  _name       text;
  _org_id     uuid;
  _invite     text;
  _member_role text;
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

  -- Resolve organization:
  --   1. Explicit organization_id from metadata (admin-created users)
  --   2. Invite code validation
  --   3. NEW: Boss auto-creates own organization
  --   4. Fallback to default org (employee only)
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

  -- Boss without org: auto-create a new organization
  IF _org_id IS NULL AND _raw_role = 'boss' THEN
    _org_id := gen_random_uuid();
    INSERT INTO public.organizations (id, name, slug, plan, invite_code, invite_code_enabled)
    VALUES (
      _org_id,
      _name || ' 的企业',
      'org-' || substr(replace(_org_id::text, '-', ''), 1, 12),
      'free',
      substr(md5(random()::text || _org_id::text), 1, 8),
      true
    );
  END IF;

  -- Employee fallback: default org
  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations WHERE slug = 'default-org' LIMIT 1;
  END IF;
  IF _org_id IS NULL THEN
    SELECT id INTO _org_id FROM public.organizations LIMIT 1;
  END IF;

  -- Determine org membership role
  _member_role := CASE WHEN _raw_role = 'boss' THEN 'owner' ELSE 'member' END;

  -- A) public.users (the table frontend reads)
  --    Note: users table has BOTH org_id (used by RLS) and organization_id columns
  INSERT INTO public.users (id, name, role, department, organization_id, org_id, created_at, updated_at)
  VALUES (NEW.id, _name, _role, _department, _org_id, _org_id, now(), now())
  ON CONFLICT (id) DO NOTHING;

  -- C) public.user_roles (RBAC compat)
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, CASE WHEN _raw_role = 'boss' THEN 'boss'::app_role ELSE 'employee'::app_role END)
  ON CONFLICT (user_id) DO NOTHING;

  -- D) organization_members (boss as owner, employee as member)
  IF _org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (_org_id, NEW.id, _member_role)
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


-- 2. Update admin_approve_boss: also set org member role to 'owner'
CREATE OR REPLACE FUNCTION public.admin_approve_boss(_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  UPDATE public.users
  SET role = 'founder', department = 'Management', updated_at = now()
  WHERE id = _user_id;

  UPDATE public.user_roles
  SET role = 'boss'
  WHERE user_id = _user_id AND role = 'pending_boss';

  -- Ensure boss is owner of their organization
  UPDATE public.organization_members
  SET role = 'owner'
  WHERE user_id = _user_id
    AND organization_id = (SELECT organization_id FROM public.users WHERE id = _user_id);

  -- Sync org_id = organization_id (RLS reads org_id)
  UPDATE public.users
  SET org_id = organization_id
  WHERE id = _user_id AND org_id IS DISTINCT FROM organization_id;
END;
$$;


-- 3. Update admin_reject_boss: migrate to default-org, clean up empty org
CREATE OR REPLACE FUNCTION public.admin_reject_boss(_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _old_org_id  uuid;
  _default_org uuid;
  _member_count int;
BEGIN
  IF NOT public.is_super_admin(auth.uid()) THEN
    RAISE EXCEPTION 'Permission denied: super_admin only';
  END IF;

  -- Get current org
  SELECT organization_id INTO _old_org_id FROM public.users WHERE id = _user_id;

  -- Find default org
  SELECT id INTO _default_org FROM public.organizations WHERE slug = 'default-org' LIMIT 1;

  -- Downgrade role
  UPDATE public.user_roles
  SET role = 'employee'
  WHERE user_id = _user_id AND role = 'pending_boss';

  -- Only migrate if old org is not default-org (i.e. it was auto-created)
  IF _old_org_id IS NOT NULL AND _default_org IS NOT NULL AND _old_org_id != _default_org THEN
    -- Move user to default org (both columns)
    UPDATE public.users
    SET organization_id = _default_org, org_id = _default_org, updated_at = now()
    WHERE id = _user_id;

    -- Update or re-create org membership
    DELETE FROM public.organization_members
    WHERE user_id = _user_id AND organization_id = _old_org_id;

    INSERT INTO public.organization_members (organization_id, user_id, role)
    VALUES (_default_org, _user_id, 'member')
    ON CONFLICT (organization_id, user_id) DO NOTHING;

    -- Clean up empty auto-created org (only if no other members remain)
    SELECT count(*) INTO _member_count
    FROM public.organization_members
    WHERE organization_id = _old_org_id;

    IF _member_count = 0 THEN
      DELETE FROM public.organizations WHERE id = _old_org_id;
    END IF;
  END IF;
END;
$$;


-- ============================================================================
-- 4. Fix RLS: founder must be scoped to own organization
--
-- The old "Users can see own documents" policy let founders see ALL documents
-- across all organizations, causing cross-tenant data leakage.
-- ============================================================================

DROP POLICY IF EXISTS "Users can see own documents" ON public.documents;
CREATE POLICY "Users can see own documents" ON public.documents
FOR SELECT USING (
  auth.uid() = owner_id
  OR (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
        AND users.role = 'founder'
        AND users.organization_id = documents.organization_id
    )
  )
);

-- 5. Sync documents.org_id from organization_id where NULL
UPDATE public.documents
SET org_id = organization_id
WHERE org_id IS NULL AND organization_id IS NOT NULL;
