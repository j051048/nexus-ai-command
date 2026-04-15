-- 1. 允许 organization_id 为 NULL（新注册用户还没有组织）
ALTER TABLE public.users ALTER COLUMN organization_id DROP NOT NULL;

-- 2. 修复触发器：新增 email、approval_status 字段，boss 注册时设为 pending
CREATE OR REPLACE FUNCTION public.handle_new_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  _role public.user_role;
  _raw_role text;
  _department text;
  _approval text;
BEGIN
  _raw_role := new.raw_user_meta_data->>'role';
  IF _raw_role = 'boss' THEN
    _role := 'founder';
    _department := 'Management';
    _approval := 'pending';
  ELSIF _raw_role = 'employee' THEN
    _role := 'sales';
    _department := 'Sales Dept';
    _approval := 'approved';
  ELSE
    _role := 'sales';
    _department := 'Sales Dept';
    _approval := 'approved';
  END IF;

  INSERT INTO public.users (id, name, email, role, department, approval_status, created_at, updated_at)
  VALUES (
    new.id,
    COALESCE(new.raw_user_meta_data->>'name', 'New User'),
    new.email,
    _role,
    _department,
    _approval,
    now(),
    now()
  )
  ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role,
    department = EXCLUDED.department,
    email = EXCLUDED.email;

  RETURN new;
END;
$$;

-- 3. 补录已注册但 public.users 缺失的 auth 用户
INSERT INTO public.users (id, name, email, role, department, approval_status, created_at, updated_at)
SELECT
  a.id,
  COALESCE(a.raw_user_meta_data->>'name', a.email),
  a.email,
  CASE WHEN a.raw_user_meta_data->>'role' = 'boss' THEN 'founder'::user_role ELSE 'sales'::user_role END,
  CASE WHEN a.raw_user_meta_data->>'role' = 'boss' THEN 'Management' ELSE 'Sales Dept' END,
  CASE WHEN a.raw_user_meta_data->>'role' = 'boss' THEN 'pending' ELSE 'approved' END,
  a.created_at,
  now()
FROM auth.users a
LEFT JOIN public.users p ON p.id = a.id
WHERE p.id IS NULL;
