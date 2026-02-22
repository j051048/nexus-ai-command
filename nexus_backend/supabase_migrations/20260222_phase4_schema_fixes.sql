-- Phase 4 schema fixes
-- 1. Create dashboard_configs table
-- 2. Add organization_id to sales_targets
-- 3. Ensure sales_metrics column aliases work

-- 1. Dashboard Configs
CREATE TABLE IF NOT EXISTS public.dashboard_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    organization_id UUID,
    config_json JSONB NOT NULL DEFAULT '{"cards":[]}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.dashboard_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own dashboard config"
    ON public.dashboard_configs
    FOR ALL
    USING (auth.uid() = user_id);

-- 2. Add organization_id to sales_targets if missing
ALTER TABLE public.sales_targets
    ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sales_targets_org ON public.sales_targets(organization_id);

-- RLS policy for sales_targets with org isolation
DROP POLICY IF EXISTS "Org members can manage targets" ON public.sales_targets;
CREATE POLICY "Org members can manage targets"
    ON public.sales_targets
    FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM public.organization_members WHERE user_id = auth.uid()
        )
    );
