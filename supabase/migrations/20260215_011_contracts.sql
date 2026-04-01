-- ============================================
-- 合同生命周期管理: 数据库迁移
-- Version: 20260215_011
-- Description: contracts 表, contract_events 表, RLS 策略
-- ============================================

-- ============================================
-- 1. 创建 contracts 表
-- ============================================
CREATE TABLE IF NOT EXISTS public.contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    customer_id UUID REFERENCES public.customers(id),
    contract_number TEXT,
    contract_type TEXT DEFAULT 'sales' CHECK (contract_type IN ('sales', 'purchase', 'service', 'nda', 'other')),
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'pending_review', 'active', 'expired', 'terminated', 'renewed')),
    amount DECIMAL(12,2),
    currency TEXT DEFAULT 'CNY',
    start_date DATE,
    end_date DATE,
    signed_by UUID REFERENCES auth.users(id),
    signed_at TIMESTAMPTZ,
    document_url TEXT,
    tags TEXT[],
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引：按组织查询
CREATE INDEX IF NOT EXISTS idx_contracts_org
    ON public.contracts(organization_id);

-- 索引：按状态查询
CREATE INDEX IF NOT EXISTS idx_contracts_status
    ON public.contracts(status);

-- 索引：按到期日查询（用于即将到期提醒）
CREATE INDEX IF NOT EXISTS idx_contracts_end_date
    ON public.contracts(end_date);

-- 索引：按合同编号查询
CREATE INDEX IF NOT EXISTS idx_contracts_number
    ON public.contracts(contract_number);

-- ============================================
-- 2. 创建 contract_events 表
-- ============================================
CREATE TABLE IF NOT EXISTS public.contract_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES public.contracts(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('created', 'submitted', 'approved', 'signed', 'amended', 'renewed', 'expired', 'terminated')),
    description TEXT,
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引：按合同查询事件
CREATE INDEX IF NOT EXISTS idx_contract_events_contract
    ON public.contract_events(contract_id);

-- 索引：按时间排序
CREATE INDEX IF NOT EXISTS idx_contract_events_created
    ON public.contract_events(created_at DESC);

-- ============================================
-- 3. 启用 RLS
-- ============================================
ALTER TABLE public.contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contract_events ENABLE ROW LEVEL SECURITY;

-- 删除已有策略（幂等）
DROP POLICY IF EXISTS "contracts_select_policy" ON public.contracts;
DROP POLICY IF EXISTS "contracts_insert_policy" ON public.contracts;
DROP POLICY IF EXISTS "contracts_update_policy" ON public.contracts;
DROP POLICY IF EXISTS "contracts_delete_policy" ON public.contracts;
DROP POLICY IF EXISTS "contract_events_select_policy" ON public.contract_events;
DROP POLICY IF EXISTS "contract_events_insert_policy" ON public.contract_events;

-- contracts: 组织成员可查看
CREATE POLICY "contracts_select_policy"
    ON public.contracts FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

-- contracts: 组织成员可创建
CREATE POLICY "contracts_insert_policy"
    ON public.contracts FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

-- contracts: 仅管理员可修改
CREATE POLICY "contracts_update_policy"
    ON public.contracts FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
              AND role IN ('boss', 'founder', 'manager')
        )
    );

-- contracts: 仅管理员可删除
CREATE POLICY "contracts_delete_policy"
    ON public.contracts FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
              AND role IN ('boss', 'founder')
        )
    );

-- contract_events: 组织成员可查看关联合同的事件
CREATE POLICY "contract_events_select_policy"
    ON public.contract_events FOR SELECT
    USING (
        contract_id IN (
            SELECT c.id FROM public.contracts c
            JOIN public.users p ON p.organization_id = c.organization_id
            WHERE p.id = auth.uid()
        )
    );

-- contract_events: 组织成员可添加事件
CREATE POLICY "contract_events_insert_policy"
    ON public.contract_events FOR INSERT
    WITH CHECK (
        contract_id IN (
            SELECT c.id FROM public.contracts c
            JOIN public.users p ON p.organization_id = c.organization_id
            WHERE p.id = auth.uid()
        )
    );
