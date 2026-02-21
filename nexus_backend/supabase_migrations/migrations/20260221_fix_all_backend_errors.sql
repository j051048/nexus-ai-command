-- ============================================================
-- Comprehensive fix for all backend errors (2026-02-21)
-- Fixes: semantic_cache columns, approval_requests columns,
--        user_token_usage columns, RPC functions, tenant_quotas
-- ============================================================

-- ============================================================
-- 1. Fix semantic_cache: add missing columns
--    p0_security_fixes dropped and recreated without user_id,
--    org_id, response_text, last_hit_at
-- ============================================================
ALTER TABLE public.semantic_cache
    ADD COLUMN IF NOT EXISTS user_id uuid REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS org_id text,
    ADD COLUMN IF NOT EXISTS response_text text,
    ADD COLUMN IF NOT EXISTS last_hit_at timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_semantic_cache_user ON public.semantic_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_semantic_cache_hash ON public.semantic_cache(query_hash);

-- ============================================================
-- 2. Fix approval_requests: add escalated boolean + timeout_at
--    Code uses .eq("escalated", False) and .lt("timeout_at", now)
-- ============================================================
ALTER TABLE public.approval_requests
    ADD COLUMN IF NOT EXISTS escalated BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS timeout_at TIMESTAMPTZ;

-- ============================================================
-- 3. Fix user_token_usage: add department_id + project_id
--    Needed for cost attribution (#30)
-- ============================================================
ALTER TABLE public.user_token_usage
    ADD COLUMN IF NOT EXISTS department_id text,
    ADD COLUMN IF NOT EXISTS project_id text;

-- ============================================================
-- 4. Fix upsert_daily_token_usage RPC
--    Accepts 7 params, writes to user_token_usage
-- ============================================================
CREATE OR REPLACE FUNCTION upsert_daily_token_usage(
    p_user_id uuid,
    p_org_id uuid,
    p_date date,
    p_tokens bigint,
    p_cost numeric,
    p_department_id text DEFAULT NULL,
    p_project_id text DEFAULT NULL
) RETURNS void AS $$
BEGIN
    INSERT INTO public.user_token_usage (
        user_id, org_id, date, total_tokens, estimated_cost_usd,
        request_count, department_id, project_id, updated_at
    )
    VALUES (
        p_user_id, p_org_id, p_date, p_tokens, p_cost,
        1, p_department_id, p_project_id, now()
    )
    ON CONFLICT (user_id, date)
    DO UPDATE SET
        total_tokens = public.user_token_usage.total_tokens + EXCLUDED.total_tokens,
        estimated_cost_usd = public.user_token_usage.estimated_cost_usd + EXCLUDED.estimated_cost_usd,
        request_count = public.user_token_usage.request_count + 1,
        org_id = COALESCE(EXCLUDED.org_id, public.user_token_usage.org_id),
        department_id = COALESCE(EXCLUDED.department_id, public.user_token_usage.department_id),
        project_id = COALESCE(EXCLUDED.project_id, public.user_token_usage.project_id),
        updated_at = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 5. Create match_semantic_cache RPC
--    Supports 4 params including p_created_after for TTL
-- ============================================================
CREATE OR REPLACE FUNCTION match_semantic_cache(
    p_query_embedding vector(1536),
    p_match_threshold float,
    p_user_id uuid,
    p_created_after timestamptz DEFAULT NULL
) RETURNS TABLE (
    id uuid,
    query_text text,
    response_text text,
    similarity float
) LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RETURN QUERY
    SELECT
        sc.id,
        sc.query_text,
        COALESCE(sc.response_text, sc.response) AS response_text,
        (1 - (sc.embedding <=> p_query_embedding))::float AS similarity
    FROM public.semantic_cache sc
    WHERE (1 - (sc.embedding <=> p_query_embedding)) > p_match_threshold
      AND sc.user_id = p_user_id
      AND (p_created_after IS NULL OR sc.created_at > p_created_after)
    ORDER BY sc.embedding <=> p_query_embedding
    LIMIT 1;
END;
$$;

-- ============================================================
-- 6. Create increment_cache_hit RPC
-- ============================================================
CREATE OR REPLACE FUNCTION increment_cache_hit(p_cache_id uuid)
RETURNS void AS $$
BEGIN
    UPDATE public.semantic_cache
    SET hit_count = hit_count + 1,
        last_hit_at = now()
    WHERE id = p_cache_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 7. Create tenant_quotas table
-- ============================================================
CREATE TABLE IF NOT EXISTS public.tenant_quotas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE NOT NULL UNIQUE,
    monthly_token_limit bigint DEFAULT 1000000,
    monthly_api_call_limit integer DEFAULT 10000,
    daily_token_limit bigint DEFAULT 100000,
    daily_api_call_limit integer DEFAULT 1000,
    rate_limit_per_minute integer DEFAULT 60,
    burst_limit integer DEFAULT 10,
    storage_limit_mb integer DEFAULT 1000,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

ALTER TABLE public.tenant_quotas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant quotas isolation" ON public.tenant_quotas
    FOR ALL USING (
        org_id = (SELECT organization_id FROM public.users WHERE id = auth.uid())
    );

-- ============================================================
-- 8. Create consume_tenant_credit RPC
-- ============================================================
CREATE OR REPLACE FUNCTION consume_tenant_credit(
    p_org_id uuid,
    p_credit_type text,
    p_amount integer,
    p_user_id uuid DEFAULT NULL
) RETURNS void AS $$
BEGIN
    UPDATE public.tenant_credits
    SET used = used + p_amount,
        updated_at = now()
    WHERE org_id = p_org_id
      AND credit_type = p_credit_type
      AND period_start <= now()
      AND period_end >= now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- 9. RLS policies for service-role writes
-- ============================================================
DROP POLICY IF EXISTS "Service can manage semantic cache" ON public.semantic_cache;
CREATE POLICY "Service can manage semantic cache" ON public.semantic_cache
    FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service can manage token usage" ON public.user_token_usage;
CREATE POLICY "Service can manage token usage" ON public.user_token_usage
    FOR ALL USING (true) WITH CHECK (true);
