-- ============================================================================
-- 组织记忆向量搜索：添加 embedding 列 + 索引 + RPC 函数
-- Date: 2026-03-25
-- Purpose: 为 org_memories 表增加向量语义搜索能力，
--          解决仅依赖 ILIKE 关键词匹配导致的低召回率问题。
-- ============================================================================

-- 1. 添加 embedding 列
ALTER TABLE public.org_memories
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- 2. 向量索引（ivfflat，org_memories 数据量小，lists=10 足够）
CREATE INDEX IF NOT EXISTS idx_org_memories_embedding
    ON public.org_memories
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- 3. 语义搜索 RPC 函数
CREATE OR REPLACE FUNCTION public.search_org_memories_by_embedding(
    p_org_id UUID,
    p_query_embedding vector(1536),
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    id BIGINT,
    organization_id UUID,
    scope VARCHAR,
    category VARCHAR,
    key VARCHAR,
    value TEXT,
    contributed_by UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        om.id,
        om.organization_id,
        om.scope,
        om.category,
        om.key,
        om.value,
        om.contributed_by,
        om.metadata,
        om.created_at,
        om.updated_at,
        (1 - (om.embedding <=> p_query_embedding))::FLOAT AS similarity
    FROM public.org_memories om
    WHERE om.organization_id = p_org_id
      AND om.embedding IS NOT NULL
      AND 1 - (om.embedding <=> p_query_embedding) > 0.3
    ORDER BY similarity DESC
    LIMIT p_limit;
END;
$$;
