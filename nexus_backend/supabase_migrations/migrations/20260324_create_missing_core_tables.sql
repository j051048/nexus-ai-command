-- ============================================================================
-- 补建第一档缺失表：工单、资产、报销、出入库记录
-- 代码中已有完整的 service/tool 层，仅缺数据库表
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- 1. 工单系统
-- ────────────────────────────────────────────────────────────────────────────

-- 1.1 工单类型
CREATE TABLE IF NOT EXISTS public.work_order_types (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    sla_hours   INTEGER NOT NULL DEFAULT 24,
    icon        TEXT,
    color       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_order_types_org
    ON public.work_order_types(organization_id);

ALTER TABLE public.work_order_types ENABLE ROW LEVEL SECURITY;

CREATE POLICY "work_order_types_org_access" ON public.work_order_types
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- 1.2 工单
CREATE TABLE IF NOT EXISTS public.work_orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    order_type      TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    priority        TEXT NOT NULL DEFAULT 'medium',
    assignee_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
    creator_id      UUID REFERENCES public.users(id) ON DELETE SET NULL,
    department_id   TEXT,
    due_date        TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_work_orders_org       ON public.work_orders(organization_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_assignee  ON public.work_orders(assignee_id);
CREATE INDEX IF NOT EXISTS idx_work_orders_status    ON public.work_orders(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_work_orders_created   ON public.work_orders(created_at DESC);

ALTER TABLE public.work_orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "work_orders_org_access" ON public.work_orders
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- 1.3 工单评论
CREATE TABLE IF NOT EXISTS public.work_order_comments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id     UUID NOT NULL REFERENCES public.work_orders(id) ON DELETE CASCADE,
    user_id      UUID REFERENCES public.users(id) ON DELETE SET NULL,
    content      TEXT,
    comment_type TEXT NOT NULL DEFAULT 'comment',
    metadata     JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wo_comments_order ON public.work_order_comments(order_id);

ALTER TABLE public.work_order_comments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "wo_comments_access" ON public.work_order_comments
    FOR ALL USING (
        order_id IN (
            SELECT id FROM public.work_orders
            WHERE organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
        )
    );

-- ────────────────────────────────────────────────────────────────────────────
-- 2. 资产管理
-- ────────────────────────────────────────────────────────────────────────────

-- 2.1 资产类型
CREATE TABLE IF NOT EXISTS public.asset_types (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    icon            TEXT,
    fields_config   JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_asset_types_org ON public.asset_types(organization_id);

ALTER TABLE public.asset_types ENABLE ROW LEVEL SECURITY;

CREATE POLICY "asset_types_org_access" ON public.asset_types
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- 2.2 资产
CREATE TABLE IF NOT EXISTS public.assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    asset_code      TEXT NOT NULL,
    name            TEXT NOT NULL,
    asset_type      TEXT,
    status          TEXT NOT NULL DEFAULT 'idle',
    department_id   TEXT,
    current_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    value           NUMERIC(12,2),
    purchase_date   DATE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_code_org
    ON public.assets(organization_id, asset_code);
CREATE INDEX IF NOT EXISTS idx_assets_org    ON public.assets(organization_id);
CREATE INDEX IF NOT EXISTS idx_assets_status ON public.assets(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_assets_user   ON public.assets(current_user_id);

ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "assets_org_access" ON public.assets
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- 2.3 资产调拨记录
CREATE TABLE IF NOT EXISTS public.asset_transfers (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    asset_id          UUID NOT NULL REFERENCES public.assets(id) ON DELETE CASCADE,
    transfer_type     TEXT NOT NULL,
    from_user_id      UUID REFERENCES public.users(id) ON DELETE SET NULL,
    to_user_id        UUID REFERENCES public.users(id) ON DELETE SET NULL,
    from_department_id TEXT,
    to_department_id   TEXT,
    reason            TEXT,
    operator_id       UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_asset_transfers_asset ON public.asset_transfers(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_transfers_org   ON public.asset_transfers(organization_id);

ALTER TABLE public.asset_transfers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "asset_transfers_org_access" ON public.asset_transfers
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- ────────────────────────────────────────────────────────────────────────────
-- 3. 报销系统
-- ────────────────────────────────────────────────────────────────────────────

-- 3.1 报销单
CREATE TABLE IF NOT EXISTS public.expense_claims (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    employee_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    claim_no        TEXT NOT NULL,
    expense_type    TEXT NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL DEFAULT 0,
    -- amount 别名，兼容 ai_insight_tools 中 select("id, amount, employee_id")
    amount          NUMERIC(12,2) GENERATED ALWAYS AS (total_amount) STORED,
    status          TEXT NOT NULL DEFAULT 'pending',
    reviewed_at     TIMESTAMPTZ,
    review_comment  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_claims_no
    ON public.expense_claims(organization_id, claim_no);
CREATE INDEX IF NOT EXISTS idx_expense_claims_org      ON public.expense_claims(organization_id);
CREATE INDEX IF NOT EXISTS idx_expense_claims_employee ON public.expense_claims(employee_id);
CREATE INDEX IF NOT EXISTS idx_expense_claims_status   ON public.expense_claims(organization_id, status);

ALTER TABLE public.expense_claims ENABLE ROW LEVEL SECURITY;

CREATE POLICY "expense_claims_org_access" ON public.expense_claims
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- 3.2 报销明细
CREATE TABLE IF NOT EXISTS public.expense_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID NOT NULL REFERENCES public.expense_claims(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    description     TEXT,
    amount          NUMERIC(12,2) NOT NULL DEFAULT 0,
    category        TEXT,
    receipt_url     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expense_items_claim ON public.expense_items(claim_id);

ALTER TABLE public.expense_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "expense_items_access" ON public.expense_items
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- ────────────────────────────────────────────────────────────────────────────
-- 4. 库存出入库记录
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.inventory_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    item_id         UUID NOT NULL REFERENCES public.inventory(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,  -- 'in' / 'out'
    quantity        INTEGER NOT NULL,
    operator_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
    receiver_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
    reason          TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inv_tx_item ON public.inventory_transactions(item_id);
CREATE INDEX IF NOT EXISTS idx_inv_tx_org  ON public.inventory_transactions(organization_id);

ALTER TABLE public.inventory_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "inv_transactions_org_access" ON public.inventory_transactions
    FOR ALL USING (
        organization_id IN (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- ────────────────────────────────────────────────────────────────────────────
-- 5. updated_at 自动触发器（复用已有 trigger 函数或新建）
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_work_orders_updated
    BEFORE UPDATE ON public.work_orders
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_assets_updated
    BEFORE UPDATE ON public.assets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_expense_claims_updated
    BEFORE UPDATE ON public.expense_claims
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
