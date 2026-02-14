-- Function to handle new user signup automatically
-- This ensures that when a user signs up via Auth, they are also created in the public.users table
CREATE OR REPLACE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$ BEGIN
INSERT INTO public.users (
        id,
        name,
        role,
        email,
        department,
        created_at,
        updated_at
    )
VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'name', new.email),
        CASE
            WHEN (new.raw_user_meta_data->>'role') = 'boss' THEN 'boss'::public.user_role
            WHEN (new.raw_user_meta_data->>'role') = 'manager' THEN 'manager'::public.user_role
            ELSE 'employee'::public.user_role
        END,
        new.email,
        COALESCE(new.raw_user_meta_data->>'department', '销售部'),
        now(),
        now()
    );
RETURN new;
EXCEPTION
WHEN unique_violation THEN RETURN new;
WHEN others THEN RAISE WARNING 'handle_new_user failed for user %: %',
new.id,
SQLERRM;
RETURN new;
END;
$$;
-- Create the trigger on auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
AFTER
INSERT ON auth.users FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();