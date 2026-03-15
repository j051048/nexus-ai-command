-- ============================================================
-- RLS 覆盖率补全: 修复无 RLS 或有 RLS 但无 Policy 的表
-- ============================================================
-- NOTE: user_wallets, sales_orders, opportunities, incentives, approvals
-- tables do not exist in production (migrations never applied).
-- Only tables confirmed to exist are covered below.
-- If those tables are created in the future, add RLS policies at creation time.

-- ── 1. 完全无 RLS 的表 ──

-- webhook_delivery_log: 含 webhook 签名，仅 service_role 可访问
ALTER TABLE public.webhook_delivery_log ENABLE ROW LEVEL SECURITY;
-- 不创建 policy = 仅 service_role 可访问（RLS 启用后默认全拒绝）

-- prompt_versions: 提示词模板，全员可读，写入由 service_role 完成
ALTER TABLE public.prompt_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "prompt_versions_read_all" ON public.prompt_versions
  FOR SELECT USING (true);

-- ── 2. 有 RLS 但无 Policy 的表 ──

-- security_events: 已启用 RLS，无 policy 是故意的（仅 service_role 写入/读取安全事件）
-- 此处添加注释确认设计意图，不需要额外 policy
COMMENT ON TABLE public.security_events IS 'Security events log. RLS enabled with no user-facing policies by design — only service_role can read/write.';
