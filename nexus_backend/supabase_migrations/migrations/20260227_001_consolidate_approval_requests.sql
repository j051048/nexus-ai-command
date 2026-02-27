-- #19: 消除重复定义 — approval_requests 表合并迁移
--
-- 发现问题:
-- 1. 20240201000000_add_business_logic.sql: 首次定义 (IF NOT EXISTS)
--    列: id, submitted_by, type(enum), amount, description, status(enum), ai_decision(enum), ai_reason, created_at
--
-- 2. 20260125130359_29e557d3-63e5-4b9d-b986-7536513a84dd.sql: 第二次定义 (无 IF NOT EXISTS!)
--    列: id, type(text), description, amount, status(text), submitted_by, submitted_at, reviewed_by, reviewed_at, ai_reason, rejection_reason, metadata
--
-- 后续 ALTER TABLE 增加的列 (来自多个迁移):
-- - chain_id, current_step, approval_level, approval_history, timeout_at, escalated (workflow_designer)
-- - form_data, form_schema_id (workflow_designer + fix_approval_and_gateway)
-- - on_behalf_of, submitted_via, approved_by, approval_comment (fix_approval_and_gateway)
-- - organization_id (add_organization_multi_tenancy)
--
-- 本迁移确保所有关键列都存在（幂等，使用 IF NOT EXISTS）

-- 确保表存在（使用最新的列定义）
CREATE TABLE IF NOT EXISTS public.approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    description TEXT,
    amount NUMERIC DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_by UUID NOT NULL,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    ai_reason TEXT,
    ai_decision TEXT DEFAULT 'manual',
    rejection_reason TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 确保所有关键列存在
DO $$
BEGIN
    -- 基础列
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='organization_id') THEN
        ALTER TABLE public.approval_requests ADD COLUMN organization_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='form_data') THEN
        ALTER TABLE public.approval_requests ADD COLUMN form_data JSONB;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='form_schema_id') THEN
        ALTER TABLE public.approval_requests ADD COLUMN form_schema_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='chain_id') THEN
        ALTER TABLE public.approval_requests ADD COLUMN chain_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='current_step') THEN
        ALTER TABLE public.approval_requests ADD COLUMN current_step INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='approval_level') THEN
        ALTER TABLE public.approval_requests ADD COLUMN approval_level TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='approval_history') THEN
        ALTER TABLE public.approval_requests ADD COLUMN approval_history JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='timeout_at') THEN
        ALTER TABLE public.approval_requests ADD COLUMN timeout_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='escalated') THEN
        ALTER TABLE public.approval_requests ADD COLUMN escalated BOOLEAN DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='on_behalf_of') THEN
        ALTER TABLE public.approval_requests ADD COLUMN on_behalf_of UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='submitted_via') THEN
        ALTER TABLE public.approval_requests ADD COLUMN submitted_via TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='approved_by') THEN
        ALTER TABLE public.approval_requests ADD COLUMN approved_by UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='approval_comment') THEN
        ALTER TABLE public.approval_requests ADD COLUMN approval_comment TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='rejection_reason') THEN
        ALTER TABLE public.approval_requests ADD COLUMN rejection_reason TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='metadata') THEN
        ALTER TABLE public.approval_requests ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='submitted_at') THEN
        ALTER TABLE public.approval_requests ADD COLUMN submitted_at TIMESTAMPTZ DEFAULT now();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='reviewed_by') THEN
        ALTER TABLE public.approval_requests ADD COLUMN reviewed_by UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='approval_requests' AND column_name='reviewed_at') THEN
        ALTER TABLE public.approval_requests ADD COLUMN reviewed_at TIMESTAMPTZ;
    END IF;
END $$;

-- 确保 RLS 已启用
ALTER TABLE public.approval_requests ENABLE ROW LEVEL SECURITY;

-- 确保关键索引存在
CREATE INDEX IF NOT EXISTS idx_approval_requests_org_id ON public.approval_requests (organization_id);
CREATE INDEX IF NOT EXISTS idx_approval_requests_submitted_by ON public.approval_requests (submitted_by);
CREATE INDEX IF NOT EXISTS idx_approval_requests_chain_id ON public.approval_requests (chain_id);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON public.approval_requests (status);
