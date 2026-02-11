-- Fix AI Settings uniqueness and organization isolation
-- 1. Ensure all existing settings have an organization_id (default to Default Org)
UPDATE public.ai_settings
SET organization_id = '00000000-0000-0000-0000-000000000000'
WHERE organization_id IS NULL;
-- 2. Add unique constraint to prevent duplicate settings for the same user in the same organization
DO $$ BEGIN IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'unique_user_org_ai_settings'
) THEN
ALTER TABLE public.ai_settings
ADD CONSTRAINT unique_user_org_ai_settings UNIQUE (user_id, organization_id);
END IF;
END $$;