-- Fix delete_employee to clear department manager references before deleting
-- Prevents FK constraint violation: departments_manager_id_fkey

CREATE OR REPLACE FUNCTION public.delete_employee(target_user_id uuid) RETURNS void AS $$ BEGIN
  -- Clear manager_id references in departments
  UPDATE public.departments SET manager_id = NULL WHERE manager_id = target_user_id;
  -- Clear manager_id references in organization_members (if applicable)
  UPDATE public.organization_members SET role = role WHERE user_id = target_user_id;
  -- Now safe to delete
  DELETE FROM public.users WHERE id = target_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
