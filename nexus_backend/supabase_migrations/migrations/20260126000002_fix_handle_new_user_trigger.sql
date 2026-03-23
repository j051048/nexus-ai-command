-- Migration: Fix handle_new_user trigger to include organization_id-- P0 Fix: "Database error saving new user" on registration
-- Root cause: handle_new_user() inserts into public.users but does NOT include
-- organization_id, which has a NOT NULL constraint.
-- 
-- This migration updates the trigger to:
-- 1. Include organization_id (defaults to '00000000-0000-0000-0000-000000000000')
-- 2. Use ON CONFLICT to handle re-runs gracefully
-- 3. Also insert into profiles and user_roles for frontend compatibility

-- Ensure default organization exists
INSERT INTO public.organizations (id, name, slug)
VALUES ('00000000-0000-0000-0000-000000000000', 'Default Org', 'default-org')
ON CONFLICT (id) DO NOTHING;

-- Replace the trigger function
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  _role_text text;
  _department text;
  _org_id uuid;
BEGIN
  -- Get role from metadata (sent from frontend)
  _role_text := NEW.raw_user_meta_data->>'role';

  -- Map frontend roles to department
  IF _role_text = 'boss' THEN
    _department := 'Management';
  ELSE
    _department := 'Sales Dept';
  END IF;

  -- Resolve organization_id: use metadata if provided, else default org
  _org_id := (NEW.raw_user_meta_data->>'organization_id')::uuid;
  IF _org_id IS NULL THEN
    _org_id := '00000000-0000-0000-0000-000000000000';
  END IF;

  -- Insert into profiles table (used by frontend supabase migrations schema)
  INSERT INTO public.profiles (user_id, name, department, organization_id)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'name', NEW.email),
    _department,
    _org_id
  )
  ON CONFLICT (user_id) DO UPDATE
  SET name = EXCLUDED.name,
      department = EXCLUDED.department;

  -- Insert into user_roles table
  INSERT INTO public.user_roles (user_id, role)
  VALUES (
    NEW.id,
    CASE WHEN _role_text = 'boss' THEN 'boss'::app_role ELSE 'employee'::app_role END
  )
  ON CONFLICT (user_id, role) DO NOTHING;

  RETURN NEW;
END;
$$;