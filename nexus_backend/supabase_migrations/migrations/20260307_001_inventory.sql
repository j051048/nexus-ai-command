-- ============================================================
-- Inventory Management Table
-- Matches InventoryPage.tsx expected schema
-- ============================================================

CREATE TABLE IF NOT EXISTS public.inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    item_code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    quantity INTEGER NOT NULL DEFAULT 0,
    min_stock INTEGER NOT NULL DEFAULT 10,
    location TEXT,
    unit TEXT DEFAULT '个',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id, item_code)
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_inventory_org_id ON public.inventory(organization_id);
CREATE INDEX IF NOT EXISTS idx_inventory_category ON public.inventory(organization_id, category);
CREATE INDEX IF NOT EXISTS idx_inventory_name ON public.inventory(organization_id, name);

-- RLS
ALTER TABLE public.inventory ENABLE ROW LEVEL SECURITY;

CREATE POLICY "inventory_org_isolation" ON public.inventory
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );

-- Auto-update updated_at
CREATE OR REPLACE TRIGGER inventory_updated_at
    BEFORE UPDATE ON public.inventory
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

COMMENT ON TABLE public.inventory IS '库存管理表 — 物料出入库与库存预警';
