-- P0 Security Fixes Migration
-- Execute this in Supabase SQL Editor

-- 1. Helper function for RLS
CREATE OR REPLACE FUNCTION get_user_org_id(p_user_id uuid) RETURNS uuid AS $$
DECLARE v_org_id uuid;
BEGIN
    SELECT organization_id INTO v_org_id FROM public.users WHERE id = p_user_id;
    RETURN v_org_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- 2. Tenant Credits Table
CREATE TABLE IF NOT EXISTS public.tenant_credits (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE NOT NULL,
    credit_type text NOT NULL,
    allocated bigint NOT NULL DEFAULT 0,
    used bigint NOT NULL DEFAULT 0,
    reserved bigint NOT NULL DEFAULT 0,
    period_start timestamptz NOT NULL,
    period_end timestamptz NOT NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(org_id, credit_type, period_start)
);

ALTER TABLE public.tenant_credits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Tenant Credits Isolation" ON public.tenant_credits;
CREATE POLICY "Tenant Credits Isolation" ON public.tenant_credits FOR ALL USING (org_id = get_user_org_id(auth.uid()));
CREATE INDEX IF NOT EXISTS idx_tenant_credits_org_type ON public.tenant_credits(org_id, credit_type);

-- 3. Agent Traces Table
CREATE TABLE IF NOT EXISTS public.agent_traces (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id text UNIQUE NOT NULL,
    thread_id text NOT NULL,
    user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    org_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL,
    query text NOT NULL,
    status text NOT NULL DEFAULT 'running',
    start_time timestamptz NOT NULL,
    end_time timestamptz,
    total_duration_ms integer,
    total_tokens integer DEFAULT 0,
    total_cost_usd numeric DEFAULT 0,
    steps_json jsonb DEFAULT '[]',
    final_response text,
    metadata_json jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);

ALTER TABLE public.agent_traces ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Agent Traces Access" ON public.agent_traces;
CREATE POLICY "Agent Traces Access" ON public.agent_traces FOR ALL USING (user_id = auth.uid() OR org_id = get_user_org_id(auth.uid()));
CREATE INDEX IF NOT EXISTS idx_agent_traces_user ON public.agent_traces(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_org ON public.agent_traces(org_id);

-- 4. Semantic Cache Table (drop first if exists to avoid column issues)
DROP TABLE IF EXISTS public.semantic_cache CASCADE;
CREATE TABLE public.semantic_cache (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_hash text UNIQUE NOT NULL,
    query_text text NOT NULL,
    embedding vector(1536),
    response text NOT NULL,
    metadata jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '1 hour'),
    hit_count integer DEFAULT 0
);

ALTER TABLE public.semantic_cache ENABLE ROW LEVEL SECURITY;
CREATE INDEX idx_semantic_cache_expires ON public.semantic_cache(expires_at);

-- 5. Security Events Table
CREATE TABLE IF NOT EXISTS public.security_events (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type text NOT NULL,
    user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    org_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL,
    ip_address text,
    user_agent text,
    details jsonb DEFAULT '{}',
    risk_score numeric DEFAULT 0,
    blocked boolean DEFAULT false,
    blocked_until timestamptz,
    timestamp timestamptz DEFAULT now()
);

ALTER TABLE public.security_events ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_security_events_ip ON public.security_events(ip_address);

-- 6. Prompt Versions Table
CREATE TABLE IF NOT EXISTS public.prompt_versions (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_id text UNIQUE NOT NULL,
    prompt_key text NOT NULL,
    content text NOT NULL,
    version_number integer NOT NULL,
    status text NOT NULL DEFAULT 'draft',
    created_by text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(prompt_key, version_number)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_key ON public.prompt_versions(prompt_key);

-- Done
SELECT 'Migration completed!' as status;

