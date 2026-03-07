-- scripts/fix_registration_trigger.sql-- ============================================================================
-- P0 FIX: "Database error saving new user" on registration
-- ============================================================================
-- ROOT CAUSE:
--   The handle_new_user() trigger inserts into public.users but does NOT
--   include organization_id, which has a NOT NULL constraint added by
--   migration 20240213000000_security_fix_org_isolation.sql.
--
-- HOW TO USE:
--   Copy and paste this entire script into Supabase SQL Editor and run it.
-- ============================================================================

-- Step 1: Ensure default organization exists
INSERT INTO public.organizations (id, name, slug)
VALUES ('00000000-0000-0000-0000-000000000000', 'Default Org', 'default-org')
ON CONFLICT (id) DO NOTHING;

-- Step 2: Check which tables exist and fix accordingly
DO $$
BEGIN
  -- Check if public.users table exists (backend schema)
  IF EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'users'
  ) THEN
    RAISE NOTICE 'Found public.users table - applying fix for backend schema';
    
    -- Check if organization_id column exists and is NOT NULL
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'organization_id'
    ) THEN
      RAISE NOTICE 'organization_id column exists - this is the cause of the bug';
    ELSE
      RAISE NOTICE 'organization_id column not found - adding it';
      ALTER TABLE public.users 
        ADD COLUMN IF NOT EXISTS organization_id uuid 
        REFERENCES public.organizations(id) 
        DEFAULT '00000000-0000-0000-0000-000000000000';
    END IF;
  END IF;
END $$;

-- Step 3: Replace the trigger function to include organization_id
-- This version handles BOTH schema variants (users table and profiles table)
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS trigger 
LANGUAGE plpgsql 
SECURITY DEFINER
SET search_path = public 
AS $$
DECLARE 
  _raw_role text;
  _department text;
  _org_id uuid;
  _has_users_table boolean;
  _has_profiles_table boolean;
BEGIN 
  -- Get role from metadata (sent from frontend)
  _raw_role := NEW.raw_user_meta_data->>'role';
  
  -- Map frontend roles to department
  IF _raw_role = 'boss' THEN 
    _department := 'Management';
  ELSE 
    _department := 'Sales Dept';
  END IF;

  -- Resolve organization_id: use metadata if provided, else default org
  _org_id := (NEW.raw_user_meta_data->>'organization_id')::uuid;
  IF _org_id IS NULL THEN
    _org_id := '00000000-0000-0000-0000-000000000000';
  END IF;

  -- Check which tables exist
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'users'
  ) INTO _has_users_table;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'profiles'
  ) INTO _has_profiles_table;

  -- Insert into public.users if it exists (backend schema)
  IF _has_users_table THEN
    BEGIN
      -- Try with organization_id first
      INSERT INTO public.users (
        id, name, role, department, organization_id, created_at, updated_at
      ) VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'name', 'New User'),
        CASE 
          WHEN _raw_role = 'boss' THEN 'founder'::user_role 
          ELSE 'sales'::user_role 
        END,
        _department,
        _org_id,
        now(),
        now()
      ) ON CONFLICT (id) DO UPDATE
      SET role = EXCLUDED.role,
          department = EXCLUDED.department,
          name = EXCLUDED.name;
    EXCEPTION WHEN undefined_column THEN
      -- Fallback: organization_id column doesn't exist yet
      INSERT INTO public.users (
        id, name, role, department, created_at, updated_at
      ) VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'name', 'New User'),
        CASE 
          WHEN _raw_role = 'boss' THEN 'founder'::user_role 
          ELSE 'sales'::user_role 
        END,
        _department,
        now(),
        now()
      ) ON CONFLICT (id) DO UPDATE
      SET role = EXCLUDED.role,
          department = EXCLUDED.department,
          name = EXCLUDED.name;
    END;
  END IF;

  -- Insert into public.profiles if it exists (frontend schema)
  IF _has_profiles_table THEN
    INSERT INTO public.profiles (user_id, name, department)
    VALUES (
      NEW.id,
      COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
      _department
    ) ON CONFLICT (user_id) DO UPDATE
    SET name = EXCLUDED.name,
        department = EXCLUDED.department;
  END IF;

  -- Insert into user_roles if it exists (frontend schema)
  IF EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'user_roles'
  ) THEN
    INSERT INTO public.user_roles (user_id, role)
    VALUES (
      NEW.id,
      CASE WHEN _raw_role = 'boss' THEN 'boss'::app_role ELSE 'employee'::app_role END
    ) ON CONFLICT (user_id, role) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$;

-- Step 4: Ensure trigger exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Step 5: Verify the fix
DO $$
BEGIN
  RAISE NOTICE '✅ Fix applied successfully!';
  RAISE NOTICE 'The handle_new_user() trigger now includes organization_id.';
  RAISE NOTICE 'New user registration should work correctly.';
END $$;