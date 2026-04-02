-- F1: Add manager role support
-- Update role check constraint to include 'manager'
-- Note: If there's no existing constraint, just add a comment documenting valid roles

-- Add manager role to role enum/check if exists
-- Valid roles: employee, manager, boss, founder, ai_assistant
COMMENT ON COLUMN users.role IS 'User role: employee | manager | boss | founder | ai_assistant';

-- F2: Add manager_id to departments table if not exists
ALTER TABLE departments ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES auth.users(id);
COMMENT ON COLUMN departments.manager_id IS 'Department manager user ID';
