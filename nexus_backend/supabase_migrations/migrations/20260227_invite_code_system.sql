-- ============================================================================
-- Feature: Invite Code System for Organization Membership
--
-- Adds invite_code columns to organizations table and a validation RPC
-- so that employees must enter a valid invite code during registration
-- to be placed in the correct organization.
-- ============================================================================

-- 1. Add invite code columns to organizations
ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS invite_code TEXT,
  ADD COLUMN IF NOT EXISTS invite_code_enabled BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS invite_code_expires_at TIMESTAMPTZ;

-- 2. Create unique index on invite_code (only for non-null values)
CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_invite_code
  ON public.organizations (invite_code)
  WHERE invite_code IS NOT NULL;

-- 3. Generate a default invite code for the default org
UPDATE public.organizations
SET invite_code = substr(md5(random()::text || id::text), 1, 8),
    invite_code_enabled = true
WHERE slug = 'default-org'
  AND invite_code IS NULL;

-- 4. RPC: Validate an invite code and return the organization_id
--    Returns NULL if code is invalid, expired, or disabled.
CREATE OR REPLACE FUNCTION public.validate_invite_code(_code TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _org_id UUID;
BEGIN
  SELECT id INTO _org_id
  FROM public.organizations
  WHERE invite_code = _code
    AND invite_code_enabled = true
    AND (invite_code_expires_at IS NULL OR invite_code_expires_at > now())
  LIMIT 1;

  RETURN _org_id;
END;
$$;

-- 5. RPC: Regenerate invite code for an organization (boss only)
CREATE OR REPLACE FUNCTION public.regenerate_invite_code(_org_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _new_code TEXT;
  _user_role TEXT;
BEGIN
  -- Check caller's role (must be boss/founder/owner)
  SELECT role INTO _user_role
  FROM public.users
  WHERE id = auth.uid();

  IF _user_role NOT IN ('founder', 'boss') THEN
    RAISE EXCEPTION 'Permission denied: only boss/founder can regenerate invite codes';
  END IF;

  -- Generate new 8-char code
  _new_code := substr(md5(random()::text || now()::text || _org_id::text), 1, 8);

  UPDATE public.organizations
  SET invite_code = _new_code,
      updated_at = now()
  WHERE id = _org_id;

  RETURN _new_code;
END;
$$;

-- 6. RPC: Toggle invite code enabled/disabled
CREATE OR REPLACE FUNCTION public.toggle_invite_code(_org_id UUID, _enabled BOOLEAN)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _user_role TEXT;
BEGIN
  SELECT role INTO _user_role
  FROM public.users
  WHERE id = auth.uid();

  IF _user_role NOT IN ('founder', 'boss') THEN
    RAISE EXCEPTION 'Permission denied';
  END IF;

  UPDATE public.organizations
  SET invite_code_enabled = _enabled,
      updated_at = now()
  WHERE id = _org_id;
END;
$$;

-- 7. Update handle_new_user to use invite code from metadata
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
  VALUES (NEW.id, CASE WHEN _raw_role = 'boss' THEN 'boss'::app_role ELSE 'employee'::app_role END)
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
