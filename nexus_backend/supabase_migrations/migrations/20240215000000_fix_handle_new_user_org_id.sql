-- Migration: Fix handle_new_user trigger to properly handle organization_id-- P0 Fix: handle_new_user trigger fails because organization_id is NOT NULL
-- but the INSERT does not include organization_id.
-- This causes "Database error saving new user" on registration.

CREATE OR REPLACE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE 
  _role public.user_role;
  _raw_role text;
  _department text;
  _org_id uuid;
BEGIN 
  -- Get role from metadata (sent from frontend)
  _raw_role := new.raw_user_meta_data->>'role';
  
  -- Map frontend roles to DB enum types and determine department
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

  -- Resolve organization_id: use metadata if provided, else default org
  _org_id := (new.raw_user_meta_data->>'organization_id')::uuid;
  IF _org_id IS NULL THEN
    _org_id := '00000000-0000-0000-0000-000000000000';
  END IF;

  -- Insert into public.users (including organization_id to satisfy NOT NULL constraint)
  INSERT INTO public.users (
    id,
    name,
    role,
    department,
    organization_id,
    created_at,
    updated_at
  )
  VALUES (
    new.id,
    COALESCE(new.raw_user_meta_data->>'name', 'New User'),
    _role,
    _department,
    _org_id,
    now(),
    now()
  ) ON CONFLICT (id) DO UPDATE
  SET role = EXCLUDED.role,
      department = EXCLUDED.department,
      organization_id = COALESCE(public.users.organization_id, EXCLUDED.organization_id);

  RETURN new;
END;
$$;