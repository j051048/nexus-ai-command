-- P2 Optimization: Semantic Cache for LLM Responses
-- Stores query-response pairs with embeddings for fast lookup of similar questions.
-- ================================================================
-- 1. Create semantic_cache table
CREATE TABLE IF NOT EXISTS public.semantic_cache (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    query_text text NOT NULL,
    response_text text NOT NULL,
    embedding vector(1536),
    -- Match OpenAI text-embedding-3-small
    user_id uuid REFERENCES auth.users(id),
    org_id text,
    -- Multi-tenancy isolation
    metadata jsonb DEFAULT '{}',
    hit_count int DEFAULT 1,
    last_hit_at timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now()
);
-- 2. Enable RLS
ALTER TABLE public.semantic_cache ENABLE ROW LEVEL SECURITY;
-- 3. RLS Policies (Tenant Isolation)
CREATE POLICY "semantic_cache_tenant_isolation" ON public.semantic_cache FOR ALL USING (
    org_id = (
        SELECT organization_id
        FROM public.users
        WHERE id = auth.uid()
    )
);
-- 4. RPC for matching semantic cache
CREATE OR REPLACE FUNCTION match_semantic_cache (
        p_query_embedding vector(1536),
        p_match_threshold float,
        p_user_id uuid
    ) RETURNS TABLE (
        id bigint,
        query_text text,
        response_text text,
        similarity float
    ) LANGUAGE plpgsql SECURITY DEFINER AS $$ BEGIN RETURN QUERY
SELECT sc.id,
    sc.query_text,
    sc.response_text,
    1 - (sc.embedding <=> p_query_embedding) AS similarity
FROM public.semantic_cache sc
WHERE 1 - (sc.embedding <=> p_query_embedding) > p_match_threshold
    AND sc.user_id = p_user_id -- Strict user-level cache or loosen to org_id if shared
ORDER BY sc.embedding <=> p_query_embedding
LIMIT 1;
END;
$$;
-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding ON public.semantic_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);