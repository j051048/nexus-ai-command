-- ============================================================================
-- 简化混合检索 RPC：移除无效的 FTS 分支
--
-- 原因: Supabase 托管环境使用 'simple' 分词器，对中文只能逐字符切分，
-- 导致 FTS 分支形同死代码。中文关键词搜索已由应用层 (jieba + ILIKE) 覆盖。
-- 保留向量语义检索 + ILIKE 实体匹配两条有效路径。
-- ============================================================================

-- ===== 1. 简化 search_memories_hybrid: 移除 FTS，仅保留向量检索 =====

CREATE OR REPLACE FUNCTION public.search_memories_hybrid(
    p_user_id UUID,
    p_query_embedding vector(1536),
    p_query_text TEXT,          -- 保留参数签名，避免破坏调用方
    p_limit INT DEFAULT 5,
    p_match_threshold FLOAT DEFAULT 0.3,
    p_org_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    organization_id UUID,
    category TEXT,
    key TEXT,
    value TEXT,
    metadata JSONB,
    importance FLOAT,
    access_count INTEGER,
    last_accessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    similarity FLOAT,
    version INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- p_query_text 不再使用 (FTS 对中文无效，关键词搜索由应用层 jieba+ILIKE 负责)
    RETURN QUERY
    SELECT
        cm.id,
        cm.user_id,
        cm.organization_id,
        cm.category,
        cm.key,
        cm.value,
        cm.metadata,
        cm.importance,
        cm.access_count,
        cm.last_accessed_at,
        cm.created_at,
        cm.updated_at,
        -- 评分 = 向量相似度 * importance * 时间衰减 (180天半衰)
        (
            (1 - (cm.embedding <=> p_query_embedding))
            * COALESCE(cm.importance, 0.5)
            * GREATEST(0.3, 1.0 - EXTRACT(EPOCH FROM (NOW() - cm.created_at)) / (180 * 86400))
        )::FLOAT AS similarity,
        cm.version
    FROM public.conversation_memories cm
    WHERE cm.user_id = p_user_id
      AND cm.embedding IS NOT NULL
      AND cm.superseded_by IS NULL
      AND (p_org_id IS NULL OR cm.organization_id = p_org_id)
      AND 1 - (cm.embedding <=> p_query_embedding) > p_match_threshold
    ORDER BY similarity DESC
    LIMIT p_limit;
END;
$$;


-- ===== 2. 简化 search_kg_triples_hybrid: 移除 FTS，仅保留 ILIKE 实体匹配 =====

CREATE OR REPLACE FUNCTION public.search_kg_triples_hybrid(
    p_org_id UUID,
    p_query_text TEXT,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_entity VARCHAR,
    relationship VARCHAR,
    destination_entity VARCHAR,
    source_type VARCHAR,
    destination_type VARCHAR,
    strength FLOAT,
    occurrences INTEGER,
    source_context TEXT,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    source_session_id TEXT,
    score FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- 仅保留 ILIKE 实体名匹配 (对中文天然友好，无分词问题)
    -- FTS 分支已移除 ('simple' 分词器对中文无效)
    RETURN QUERY
    SELECT
        t.id,
        t.source_entity,
        t.relationship,
        t.destination_entity,
        t.source_type,
        t.destination_type,
        t.strength,
        t.occurrences,
        t.source_context,
        t.valid_from,
        t.valid_to,
        t.source_session_id,
        -- 评分 = strength * log(occurrences+1)
        (t.strength * LN(t.occurrences + 1))::FLOAT AS score
    FROM public.knowledge_graph_triples t
    WHERE t.organization_id = p_org_id
      AND t.valid_to IS NULL
      AND (
          t.source_entity ILIKE '%' || p_query_text || '%'
          OR t.destination_entity ILIKE '%' || p_query_text || '%'
          OR t.relationship ILIKE '%' || p_query_text || '%'
      )
    ORDER BY score DESC
    LIMIT p_limit;
END;
$$;
