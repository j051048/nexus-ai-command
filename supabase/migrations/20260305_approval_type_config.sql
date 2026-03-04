-- 审批类型注册表 — 数据库驱动的审批类型配置，替代硬编码 VALID_APPROVAL_TYPES
CREATE TABLE IF NOT EXISTS public.approval_type_config (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,

  -- 类型标识
  type_code TEXT NOT NULL,
  type_name TEXT NOT NULL,
  icon TEXT DEFAULT 'FileCheck',
  category TEXT DEFAULT 'general',

  -- 审批链配置
  default_chain_key TEXT,
  amount_field BOOLEAN DEFAULT true,

  -- 数据源（解决双表问题）
  source_table TEXT DEFAULT 'approval_requests',

  -- 控制
  is_active BOOLEAN DEFAULT true,
  sort_order INT DEFAULT 0,

  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),

  UNIQUE(organization_id, type_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_atc_org_active
  ON public.approval_type_config(organization_id, is_active, sort_order);

-- RLS
ALTER TABLE public.approval_type_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_members_can_read_type_config"
ON public.approval_type_config FOR SELECT
USING (
  organization_id IN (
    SELECT organization_id FROM public.users WHERE id = auth.uid()
  )
);

CREATE POLICY "admins_can_manage_type_config"
ON public.approval_type_config FOR ALL
USING (
  organization_id IN (
    SELECT organization_id FROM public.users
    WHERE id = auth.uid() AND role IN ('boss', 'founder')
  )
);

-- 预置默认审批类型（按组织 seed）
CREATE OR REPLACE FUNCTION seed_default_approval_types(p_org_id UUID)
RETURNS void AS $$
BEGIN
  INSERT INTO public.approval_type_config
    (organization_id, type_code, type_name, icon, category, default_chain_key, amount_field, source_table, sort_order)
  VALUES
    (p_org_id, 'expense',       '费用报销', 'Receipt',       'finance',  'expense',  true,  'approval_requests',  10),
    (p_org_id, 'travel',        '出差申请', 'Plane',         'general',  'expense',  true,  'approval_requests',  20),
    (p_org_id, 'purchase',      '采购申请', 'ShoppingCart',  'finance',  'purchase', true,  'approval_requests',  30),
    (p_org_id, 'leave',         '请假申请', 'Calendar',      'oa',       'default',  false, 'oa_leave_requests',  40),
    (p_org_id, 'contract',      '合同审批', 'FileSignature', 'general',  'default',  true,  'approval_requests',  50),
    (p_org_id, 'overtime',      '加班申请', 'Clock',         'oa',       'default',  false, 'approval_requests',  60),
    (p_org_id, 'business_trip', '商务出行', 'Briefcase',     'general',  'expense',  true,  'approval_requests',  70)
  ON CONFLICT (organization_id, type_code) DO NOTHING;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- updated_at 自动更新触发器
CREATE OR REPLACE TRIGGER update_approval_type_config_updated_at
  BEFORE UPDATE ON public.approval_type_config
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
