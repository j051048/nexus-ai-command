-- Add employee_number column to users table
-- 员工工号字段，老板可编辑
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS employee_number text;

-- Optional: create index for faster lookup by employee_number within org
CREATE INDEX IF NOT EXISTS idx_users_employee_number
  ON public.users (organization_id, employee_number)
  WHERE employee_number IS NOT NULL;
