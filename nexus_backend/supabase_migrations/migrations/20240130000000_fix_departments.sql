-- 1. Update the Trigger Function to handle departments better
CREATE OR REPLACE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE _role public.user_role;
_raw_role text;
_department text;
BEGIN -- Get role from metadata (sent from frontend)
_raw_role := new.raw_user_meta_data->>'role';
-- Map frontend roles to DB enum types and determine department
IF _raw_role = 'boss' THEN _role := 'founder';
_department := 'Management';
-- Bosses belong to Management
ELSIF _raw_role = 'employee' THEN _role := 'sales';
_department := 'Sales Dept';
ELSE _role := 'sales';
_department := 'Sales Dept';
END IF;
-- Insert into public.users
INSERT INTO public.users (
        id,
        name,
        role,
        department,
        created_at,
        updated_at
    )
VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'name', 'New User'),
        _role,
        _department,
        now(),
        now()
    );
RETURN new;
END;
$$;
-- 2. Data Patch: Fix existing users who are 'founder' but have wrong department
UPDATE public.users
SET department = 'Management'
WHERE role = 'founder'
    AND department = 'Sales Dept';
-- 3. Data Patch: Ensure 'Sales Dept' for sales roles if null
UPDATE public.users
SET department = 'Sales Dept'
WHERE role = 'sales'
    AND department IS NULL;