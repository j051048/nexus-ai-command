-- ============================================================================
-- 记忆系统 Hindsight 借鉴优化：fact_type + confidence + valid_until
--
-- 1. fact_type: 区分 fact / opinion / experience 三种记忆类型
-- 2. confidence: 观点置信度 (0-1)，用于检索加权
-- 3. valid_until: 时间区间结束日期（与 valid_from 配合）
-- 4. 更新 RPC 函数返回新列并在评分中使用 confidence
-- ============================================================================

-- ===== 1. 新增列 =====

ALTER TABLE conversation_memories
  ADD COLUMN IF NOT EXISTS fact_type TEXT DEFAULT 'fact',
  ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ;

-- 观点类记忆的部分索引（快速查询低置信度观点）
CREATE INDEX IF NOT EXISTS idx_memories_opinions
  ON conversation_memories (user_id, confidence)
  WHERE fact_type = 'opinion' AND superseded_by IS NULL;

-- ===== 2. 更新 search_memories_by_embedding：返回新列 + confidence 加权 =====

CREATE OR REPLACE FUNCTION public.search_memories_by_embedding(
    query_embedding vector(1536),
    match_user_id UUID,
    match_limit INT DEFAULT 5,
    match_org_id UUID DEFAULT NULL
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
    fact_type TEXT,
    confidence FLOAT,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    embedding vector(1536)
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
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
        -- similarity * importance * time_decay * confidence
        (
            (1 - (cm.embedding <=> query_embedding))
            * COALESCE(cm.importance, 0.5)
            * GREATEST(0.3, 1.0 - EXTRACT(EPOCH FROM (NOW() - cm.created_at)) / (180 * 86400))
            * COALESCE(cm.confidence, 1.0)
        )::FLOAT AS similarity,
        cm.fact_type,
        cm.confidence,
        cm.valid_from,
        cm.valid_until,
        cm.embedding
    FROM public.conversation_memories cm
    WHERE cm.user_id = match_user_id
      AND cm.embedding IS NOT NULL
      AND cm.superseded_by IS NULL
      AND (match_org_id IS NULL OR cm.organization_id = match_org_id)
      AND 1 - (cm.embedding <=> query_embedding) > 0.3
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;

-- ===== 3. 更新 search_memories_hybrid：返回新列 + confidence 加权 =====

CREATE OR REPLACE FUNCTION public.search_memories_hybrid(
    p_user_id UUID,
    p_query_embedding vector(1536),
    p_query_text TEXT,
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
    version INTEGER,
    fact_type TEXT,
    confidence FLOAT,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    embedding vector(1536)
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
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
        (
            (1 - (cm.embedding <=> p_query_embedding))
            * COALESCE(cm.importance, 0.5)
            * GREATEST(0.3, 1.0 - EXTRACT(EPOCH FROM (NOW() - cm.created_at)) / (180 * 86400))
            * COALESCE(cm.confidence, 1.0)
        )::FLOAT AS similarity,
        cm.version,
        cm.fact_type,
        cm.confidence,
        cm.valid_from,
        cm.valid_until,
        cm.embedding
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
