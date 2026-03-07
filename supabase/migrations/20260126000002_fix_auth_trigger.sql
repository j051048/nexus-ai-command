-- Migration: Fix auth trigger to use profiles + user_roles tables-- Fix: Ensure handle_new_user() trigger inserts into the correct tables
-- The project uses public.profiles + public.user_roles (not public.users)
-- This migration ensures the auth trigger is consistent with the actual schema.

-- Recreate the handle_new_user function to target profiles + user_roles
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Insert into profiles table
  INSERT INTO public.profiles (user_id, name)
  VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'name', NEW.email));

  -- Insert into user_roles table
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, COALESCE((NEW.raw_user_meta_data->>'role')::app_role, 'employee'));

  RETURN NEW;
EXCEPTION
  WHEN unique_violation THEN
    -- User already exists (e.g. from a previous partial signup), skip gracefully
    RETURN NEW;
  WHEN OTHERS THEN
    -- Log but don't block auth signup
    RAISE WARNING 'handle_new_user failed for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

-- Recreate the trigger (drop first to ensure clean state)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();