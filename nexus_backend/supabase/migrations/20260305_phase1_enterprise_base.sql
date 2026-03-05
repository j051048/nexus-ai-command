-- ============================================================================
-- Phase 1: 企业基础设施层
-- 新增9张表 + 补充departments列: 系统配置、组织架构、资产管理、工单系统
-- 注意: departments 表已存在且 id 为 TEXT 类型，所有外键引用用 TEXT
-- ============================================================================

-- 1. 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  config_type TEXT NOT NULL,
  config_key TEXT NOT NULL,
  config_value JSONB NOT NULL,
  sort_order INT DEFAULT 0,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(organization_id, config_type, config_key)
);
CREATE INDEX IF NOT EXISTS idx_system_configs_org_type ON system_configs(organization_id, config_type);

-- 2. 补充 departments 缺少的列
ALTER TABLE departments ADD COLUMN IF NOT EXISTS sort_order INT DEFAULT 0;
ALTER TABLE departments ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';

-- 3. 职位表 (department_id TEXT 匹配 departments.id)
CREATE TABLE IF NOT EXISTS positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  level INT DEFAULT 1,
  department_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(organization_id, name)
);
CREATE INDEX IF NOT EXISTS idx_positions_org ON positions(organization_id);

-- 4. 员工表 (department_id TEXT)
CREATE TABLE IF NOT EXISTS employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  department_id TEXT NOT NULL,
  position_id UUID REFERENCES positions(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  hire_date DATE,
  resign_date DATE,
  status TEXT DEFAULT 'active',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_employees_org ON employees(organization_id);
CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department_id);
CREATE INDEX IF NOT EXISTS idx_employees_user ON employees(user_id);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);

-- 5. 资产类型表
CREATE TABLE IF NOT EXISTS asset_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  icon TEXT,
  fields_config JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(organization_id, name)
);
CREATE INDEX IF NOT EXISTS idx_asset_types_org ON asset_types(organization_id);

-- 6. 资产表 (department_id TEXT)
CREATE TABLE IF NOT EXISTS assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  asset_code TEXT NOT NULL,
  name TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  status TEXT DEFAULT 'idle',
  department_id TEXT,
  current_user_id UUID REFERENCES employees(id) ON DELETE SET NULL,
  purchase_date DATE,
  value NUMERIC(12,2),
  depreciation_rate NUMERIC(5,2),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(organization_id, asset_code)
);
CREATE INDEX IF NOT EXISTS idx_assets_org ON assets(organization_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_dept ON assets(department_id);
CREATE INDEX IF NOT EXISTS idx_assets_user ON assets(current_user_id);

-- 7. 资产转移记录表
CREATE TABLE IF NOT EXISTS asset_transfers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  transfer_type TEXT NOT NULL,
  from_user_id UUID REFERENCES employees(id) ON DELETE SET NULL,
  to_user_id UUID REFERENCES employees(id) ON DELETE SET NULL,
  from_department_id TEXT,
  to_department_id TEXT,
  reason TEXT,
  operator_id UUID NOT NULL REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_asset_transfers_org ON asset_transfers(organization_id);
CREATE INDEX IF NOT EXISTS idx_asset_transfers_asset ON asset_transfers(asset_id);

-- 8. 工单类型表
CREATE TABLE IF NOT EXISTS work_order_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  sla_hours INT DEFAULT 24,
  auto_assign_rule JSONB DEFAULT '{}',
  icon TEXT,
  color TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(organization_id, name)
);
CREATE INDEX IF NOT EXISTS idx_work_order_types_org ON work_order_types(organization_id);

-- 9. 工单表 (department_id TEXT)
CREATE TABLE IF NOT EXISTS work_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  order_type TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  priority TEXT DEFAULT 'medium',
  status TEXT DEFAULT 'open',
  creator_id UUID NOT NULL REFERENCES auth.users(id),
  assignee_id UUID REFERENCES employees(id) ON DELETE SET NULL,
  department_id TEXT,
  due_date TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_work_orders_org ON work_orders(organization_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_type ON work_orders(order_type);
CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status);
CREATE INDEX IF NOT EXISTS idx_work_orders_creator ON work_orders(creator_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_assignee ON work_orders(assignee_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_dept ON work_orders(department_id);

-- 10. 工单评论表
CREATE TABLE IF NOT EXISTS work_order_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id),
  content TEXT NOT NULL,
  comment_type TEXT DEFAULT 'comment',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_work_order_comments_order ON work_order_comments(order_id);

-- 11. RLS 策略
ALTER TABLE system_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_transfers ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_order_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_order_comments ENABLE ROW LEVEL SECURITY;

-- 组织隔离策略
CREATE POLICY system_configs_org ON system_configs FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY positions_org ON positions FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY employees_org ON employees FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY asset_types_org ON asset_types FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY assets_org ON assets FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY asset_transfers_org ON asset_transfers FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY work_order_types_org ON work_order_types FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY work_orders_org ON work_orders FOR ALL USING (organization_id = get_user_org_id(auth.uid()));
CREATE POLICY work_order_comments_org ON work_order_comments FOR ALL USING (order_id IN (SELECT id FROM work_orders WHERE organization_id = get_user_org_id(auth.uid())));

-- Service role 策略
CREATE POLICY system_configs_service ON system_configs FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY positions_service ON positions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY employees_service ON employees FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY asset_types_service ON asset_types FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY assets_service ON assets FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY asset_transfers_service ON asset_transfers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY work_order_types_service ON work_order_types FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY work_orders_service ON work_orders FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY work_order_comments_service ON work_order_comments FOR ALL USING (auth.role() = 'service_role');
