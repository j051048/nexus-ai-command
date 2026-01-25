-- Function to handle new user signup automatically
-- This ensures that when a user signs up via Auth, they are also created in the public.users table
CREATE OR REPLACE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE _role public.user_role;
_raw_role text;
BEGIN -- Get role from metadata (sent from frontend)
_raw_role := new.raw_user_meta_data->>'role';
-- Map frontend roles to DB enum types
-- Frontend sends: 'boss' | 'employee'
-- DB Enum supports: 'founder' | 'sales' | 'employee'
IF _raw_role = 'boss' THEN _role := 'founder';
ELSIF _raw_role = 'employee' THEN _role := 'sales';
-- Map employee to sales role by default
ELSE _role := 'sales';
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
        'Sales Dept',
        -- Default department
        now(),
        now()
    );
RETURN new;
END;
$$;
-- Create the trigger on auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
AFTER
INSERT ON auth.users FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();