-- Fix employee management: add job_title column, admin_update_user RPC, fix get_user_role
-- 修复员工管理：添加 job_title 列、管理员更新用户 RPC、修复角色识别函数

-- 1. 添加 job_title 列（前端已使用该字段名，DB 仅有 title 列）
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS job_title TEXT;

-- 2. 创建 admin_update_user SECURITY DEFINER 函数
--    绕过 RLS 的 id = auth.uid() 限制，允许 boss/founder 更新其他用户
CREATE OR REPLACE FUNCTION public.admin_update_user(
  target_user_id UUID,
  new_role TEXT DEFAULT NULL,
  new_department TEXT DEFAULT NULL,
  new_job_title TEXT DEFAULT NULL,
  new_employee_number TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  caller_role public.user_role;
  result JSONB;
BEGIN
  -- 权限检查：仅 founder/boss 可调用
  SELECT role INTO caller_role FROM public.users WHERE id = auth.uid();
  IF caller_role NOT IN ('founder', 'boss') THEN
    RAISE EXCEPTION 'Permission denied: only boss can update other users';
  END IF;

  -- 更新非 NULL 字段
  UPDATE public.users SET
    role = COALESCE(new_role::public.user_role, role),
    department = COALESCE(new_department, department),
    job_title = COALESCE(new_job_title, job_title),
    employee_number = COALESCE(new_employee_number, employee_number),
    updated_at = NOW()
  WHERE id = target_user_id;

  SELECT to_jsonb(u) INTO result FROM public.users u WHERE u.id = target_user_id;
  RETURN result;
END;
$$;

-- 3. 修复 get_user_role RPC：添加 boss 和 manager 的正确映射
CREATE OR REPLACE FUNCTION public.get_user_role(_user_id uuid) RETURNS text AS $$
DECLARE _role public.user_role;
BEGIN
  SELECT role INTO _role FROM public.users WHERE id = _user_id;
  IF _role IS NULL THEN RETURN 'employee';
  ELSIF _role = 'founder' THEN RETURN 'boss';
  ELSIF _role = 'boss' THEN RETURN 'boss';
  ELSIF _role = 'manager' THEN RETURN 'manager';
  ELSIF _role = 'ai_assistant' THEN RETURN 'ai_assistant';
  ELSE RETURN 'employee';
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
