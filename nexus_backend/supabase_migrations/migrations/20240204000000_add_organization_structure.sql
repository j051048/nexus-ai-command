-- P2 Optimization: Organization Structure Tables
-- Adds support for multi-level approval chains and department hierarchy

-- =====================================================
-- 1. Departments Table (Hierarchical)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    parent_id TEXT REFERENCES public.departments(id),
    manager_id UUID REFERENCES public.users(id),
    budget_annual NUMERIC(14, 2) DEFAULT 0,
    cost_center TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for hierarchical queries
CREATE INDEX IF NOT EXISTS idx_departments_parent ON public.departments(parent_id);
CREATE INDEX IF NOT EXISTS idx_departments_manager ON public.departments(manager_id);

-- Enable RLS
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;

-- Everyone can read departments
CREATE POLICY "Departments are viewable by authenticated users" ON public.departments
    FOR SELECT USING (auth.role() = 'authenticated');

-- Only founders can modify departments
CREATE POLICY "Founders can manage departments" ON public.departments
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE id = auth.uid() AND role = 'founder'
        )
    );

-- =====================================================
-- 2. Add manager_id to users table
-- =====================================================
ALTER TABLE public.users 
    ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS department_id TEXT REFERENCES public.departments(id),
    ADD COLUMN IF NOT EXISTS hire_date DATE,
    ADD COLUMN IF NOT EXISTS title TEXT;

CREATE INDEX IF NOT EXISTS idx_users_manager ON public.users(manager_id);
CREATE INDEX IF NOT EXISTS idx_users_department ON public.users(department_id);

-- =====================================================
-- 3. Approval Chains Table
-- =====================================================
CREATE TABLE IF NOT EXISTS public.approval_chains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    applies_to TEXT[] NOT NULL DEFAULT ARRAY['*'],
    steps JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.approval_chains ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Approval chains are viewable by authenticated users" ON public.approval_chains
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Founders can manage approval chains" ON public.approval_chains
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE id = auth.uid() AND role = 'founder'
        )
    );

-- =====================================================
-- 4. Enhanced Approval Requests Table
-- =====================================================
ALTER TABLE public.approval_requests
    ADD COLUMN IF NOT EXISTS chain_id UUID REFERENCES public.approval_chains(id),
    ADD COLUMN IF NOT EXISTS current_step INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS approval_level TEXT,
    ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS escalation_reason TEXT,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES public.users(id),
    ADD COLUMN IF NOT EXISTS approval_history JSONB DEFAULT '[]';

-- =====================================================
-- 5. Event Log Table (for Event Bus persistence)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.event_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    user_id UUID REFERENCES public.users(id),
    metadata JSONB DEFAULT '{}',
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_log_type ON public.event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_user ON public.event_log(user_id);
CREATE INDEX IF NOT EXISTS idx_event_log_processed ON public.event_log(processed);
CREATE INDEX IF NOT EXISTS idx_event_log_created ON public.event_log(created_at DESC);

-- Enable RLS
ALTER TABLE public.event_log ENABLE ROW LEVEL SECURITY;

-- Only system and founders can access event log
CREATE POLICY "Event log access for founders" ON public.event_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE id = auth.uid() AND role = 'founder'
        )
    );

-- =====================================================
-- 6. User Token Usage Table (for Token Tracking)
-- =====================================================
CREATE TABLE IF NOT EXISTS public.user_token_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    total_tokens BIGINT DEFAULT 0,
    estimated_cost_usd NUMERIC(10, 6) DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    model_usage JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_token_usage_user_date ON public.user_token_usage(user_id, date DESC);

-- Enable RLS
ALTER TABLE public.user_token_usage ENABLE ROW LEVEL SECURITY;

-- Users can see their own usage
CREATE POLICY "Users can view own token usage" ON public.user_token_usage
    FOR SELECT USING (auth.uid() = user_id);

-- Founders can see all usage
CREATE POLICY "Founders can view all token usage" ON public.user_token_usage
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE id = auth.uid() AND role = 'founder'
        )
    );

-- =====================================================
-- 7. Helper Functions
-- =====================================================

-- Function to get department hierarchy path
CREATE OR REPLACE FUNCTION get_department_path(dept_id TEXT)
RETURNS TEXT[] AS $$
DECLARE
    path TEXT[] := ARRAY[]::TEXT[];
    current_id TEXT := dept_id;
    current_name TEXT;
BEGIN
    WHILE current_id IS NOT NULL LOOP
        SELECT name, parent_id INTO current_name, current_id
        FROM public.departments WHERE id = current_id;
        
        IF current_name IS NOT NULL THEN
            path := array_prepend(current_name, path);
        END IF;
    END LOOP;
    RETURN path;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get user's reporting chain
CREATE OR REPLACE FUNCTION get_reporting_chain(p_user_id UUID)
RETURNS TABLE(user_id UUID, user_name TEXT, user_role TEXT, level INT) AS $$
DECLARE
    current_id UUID := p_user_id;
    lvl INT := 0;
BEGIN
    WHILE current_id IS NOT NULL AND lvl < 10 LOOP
        RETURN QUERY
        SELECT u.id, u.name, u.role::TEXT, lvl
        FROM public.users u WHERE u.id = current_id;
        
        SELECT u.manager_id INTO current_id
        FROM public.users u WHERE u.id = current_id;
        
        lvl := lvl + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to increment user bonus (for event handlers)
CREATE OR REPLACE FUNCTION increment_user_bonus(p_user_id UUID, p_amount NUMERIC)
RETURNS VOID AS $$
BEGIN
    UPDATE public.users
    SET total_bonus = COALESCE(total_bonus, 0) + p_amount,
        updated_at = NOW()
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 8. Seed Default Departments
-- =====================================================
INSERT INTO public.departments (id, name, description) VALUES
    ('executive', '高管层', '公司决策层'),
    ('sales', '销售部', '负责产品销售与客户关系'),
    ('sales_domestic', '国内销售组', '负责国内市场销售'),
    ('sales_international', '海外销售组', '负责海外市场拓展'),
    ('engineering', '研发部', '负责产品研发与技术创新'),
    ('product', '产品部', '负责产品规划与设计'),
    ('finance', '财务部', '负责财务管理与审计'),
    ('hr', '人力资源部', '负责人才招聘与员工发展'),
    ('operations', '运营部', '负责日常运营管理')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- Set parent relationships
UPDATE public.departments SET parent_id = 'sales' WHERE id IN ('sales_domestic', 'sales_international');

-- =====================================================
-- 9. Seed Default Approval Chains
-- =====================================================
INSERT INTO public.approval_chains (name, description, applies_to, steps) VALUES
(
    '费用报销审批链',
    '适用于差旅、招待等费用报销',
    ARRAY['expense', 'travel', 'entertainment'],
    '[
        {"level": "auto", "threshold": 500, "approver_role": "system", "timeout_hours": 0},
        {"level": "manager", "threshold": 5000, "approver_role": "manager", "timeout_hours": 24},
        {"level": "director", "threshold": 20000, "approver_role": "director", "timeout_hours": 48},
        {"level": "cfo", "threshold": 100000, "approver_role": "cfo", "timeout_hours": 72},
        {"level": "ceo", "threshold": 999999999, "approver_role": "ceo", "timeout_hours": 168}
    ]'::jsonb
),
(
    '采购审批链',
    '适用于设备、软件等采购申请',
    ARRAY['purchase', 'procurement'],
    '[
        {"level": "auto", "threshold": 2000, "approver_role": "system", "timeout_hours": 0},
        {"level": "manager", "threshold": 15000, "approver_role": "manager", "timeout_hours": 24},
        {"level": "director", "threshold": 50000, "approver_role": "director", "timeout_hours": 48},
        {"level": "cfo", "threshold": 200000, "approver_role": "cfo", "timeout_hours": 72},
        {"level": "board", "threshold": 999999999, "approver_role": "board", "timeout_hours": 336}
    ]'::jsonb
),
(
    '默认审批链',
    '通用审批流程',
    ARRAY['*'],
    '[
        {"level": "auto", "threshold": 1000, "approver_role": "system", "timeout_hours": 0},
        {"level": "manager", "threshold": 10000, "approver_role": "manager", "timeout_hours": 24},
        {"level": "ceo", "threshold": 999999999, "approver_role": "founder", "timeout_hours": 72}
    ]'::jsonb
)
ON CONFLICT DO NOTHING;

-- Update timestamps trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_departments_modtime
    BEFORE UPDATE ON public.departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_approval_chains_modtime
    BEFORE UPDATE ON public.approval_chains
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_token_usage_modtime
    BEFORE UPDATE ON public.user_token_usage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();