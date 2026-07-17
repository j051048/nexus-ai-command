-- Scientific-instrument product taxonomy and structured growth context.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.instrument_line_catalog (
    code text PRIMARY KEY,
    name text NOT NULL,
    sort_order integer NOT NULL,
    description text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.instrument_line_catalog (code, name, sort_order, description)
VALUES
    ('spectroscopy', '光谱', 10, '光学响应、元素与分子结构分析仪器'),
    ('chromatography', '色谱', 20, '复杂混合物分离与定量分析仪器'),
    ('mass_spectrometry', '质谱', 30, '基于质荷比的高灵敏分析仪器'),
    ('energy_spectroscopy', '能谱', 40, '射线和电子能量分布分析仪器'),
    ('electronic_instrumentation', '电子与高科技科学仪器', 50, '电子、通信、半导体和自动化测试仪器')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    sort_order = EXCLUDED.sort_order,
    description = EXCLUDED.description;

CREATE TABLE IF NOT EXISTS public.instrument_product_catalog (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    instrument_line_code text NOT NULL REFERENCES public.instrument_line_catalog(code),
    product_name text NOT NULL,
    model_code text,
    positioning text,
    application_fields text[] NOT NULL DEFAULT '{}',
    key_specs jsonb NOT NULL DEFAULT '{}'::jsonb,
    competitor_models text[] NOT NULL DEFAULT '{}',
    knowledge_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, model_code)
);

ALTER TABLE public.business_clue
    ADD COLUMN IF NOT EXISTS instrument_line_code text REFERENCES public.instrument_line_catalog(code),
    ADD COLUMN IF NOT EXISTS application_field text,
    ADD COLUMN IF NOT EXISTS product_interest text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS purchase_stage text,
    ADD COLUMN IF NOT EXISTS budget_source text,
    ADD COLUMN IF NOT EXISTS competitor_models text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.customers
    ADD COLUMN IF NOT EXISTS instrument_line_code text REFERENCES public.instrument_line_catalog(code),
    ADD COLUMN IF NOT EXISTS instrument_line_codes text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS application_fields text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS purchase_stage text,
    ADD COLUMN IF NOT EXISTS budget_source text,
    ADD COLUMN IF NOT EXISTS installed_base jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS competitor_models text[] NOT NULL DEFAULT '{}';

ALTER TABLE public.bid_project
    ADD COLUMN IF NOT EXISTS instrument_line_code text REFERENCES public.instrument_line_catalog(code),
    ADD COLUMN IF NOT EXISTS application_field text,
    ADD COLUMN IF NOT EXISTS target_product_models text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS competitor_models text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS scoring_matrix jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.vmd_main_task
    ADD COLUMN IF NOT EXISTS instrument_line_code text REFERENCES public.instrument_line_catalog(code),
    ADD COLUMN IF NOT EXISTS application_field text,
    ADD COLUMN IF NOT EXISTS target_product_models text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS domain_context jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_instrument_products_org_line
    ON public.instrument_product_catalog (organization_id, instrument_line_code, is_active);
CREATE INDEX IF NOT EXISTS idx_business_clue_instrument_line
    ON public.business_clue (tenant_id, instrument_line_code, status);
CREATE INDEX IF NOT EXISTS idx_customers_instrument_line
    ON public.customers (organization_id, instrument_line_code, stage);
CREATE INDEX IF NOT EXISTS idx_bid_project_instrument_line
    ON public.bid_project (tenant_id, instrument_line_code, status);
CREATE INDEX IF NOT EXISTS idx_vmd_task_instrument_line
    ON public.vmd_main_task (tenant_id, instrument_line_code, status);

ALTER TABLE public.instrument_line_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.instrument_product_catalog ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS instrument_line_catalog_read ON public.instrument_line_catalog;
CREATE POLICY instrument_line_catalog_read ON public.instrument_line_catalog
    FOR SELECT USING (true);

DROP POLICY IF EXISTS instrument_product_catalog_tenant_isolation ON public.instrument_product_catalog;
CREATE POLICY instrument_product_catalog_tenant_isolation ON public.instrument_product_catalog
    FOR ALL USING (organization_id::text = public.current_tenant_id_text())
    WITH CHECK (organization_id::text = public.current_tenant_id_text());
