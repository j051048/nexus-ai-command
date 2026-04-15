-- Admin panel: boss 审批流程需要 approval_status 列
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS approval_status text NOT NULL DEFAULT 'approved';

-- 已有用户默认 approved，新注册 boss 由注册逻辑设为 pending
COMMENT ON COLUMN public.users.approval_status IS 'pending | approved | rejected — 用于 admin 审批流程';
