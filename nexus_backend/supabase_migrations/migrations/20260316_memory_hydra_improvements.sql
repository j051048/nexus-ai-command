-- ============================================================================
-- Migration: Hydra DB-inspired Memory Improvements
-- Date: 2026-03-16
-- Purpose: 4 项记忆系统改良
--   P0: 记忆版本追踪（追加而非覆盖）
--   P1: conversation_memories 全文搜索 + 混合检索 RPC
--   P2: chunk enriched_content 列
--   P3: 检索时间衰减权重（SQL 层）
-- ============================================================================

-- ===== P0: 记忆版本追踪 =====

-- 新增 version 列和 superseded_by 指针
ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS superseded_by UUID REFERENCES public.conversation_memories(id);

-- 快速找最新版本记忆的索引
CREATE INDEX IF NOT EXISTS idx_memories_latest
    ON public.conversation_memories(user_id, key)
    WHERE superseded_by IS NULL;


-- ===== P1: 全文搜索 =====

-- FTS 生成列 (simple 分词器对中文友好)
ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS fts tsvector
    GENERATED ALWAYS AS (
        to_tsvector('simple', COALESCE(key, '') || ' ' || COALESCE(value, ''))
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_memories_fts
    ON public.conversation_memories USING GIN(fts);

-- 混合检索 RPC: 向量 + FTS，RRF 融合评分 + 时间衰减 (P3)
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
    version INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    k CONSTANT INT := 60;  -- RRF constant
BEGIN
    RETURN QUERY
    WITH
    -- 向量语义检索
    vec AS (
        SELECT cm.id,
               ROW_NUMBER() OVER (ORDER BY cm.embedding <=> p_query_embedding) AS rank_pos,
               1 - (cm.embedding <=> p_query_embedding) AS vec_sim
        FROM public.conversation_memories cm
        WHERE cm.user_id = p_user_id
          AND cm.embedding IS NOT NULL
          AND cm.superseded_by IS NULL
          AND (p_org_id IS NULL OR cm.organization_id = p_org_id)
          AND 1 - (cm.embedding <=> p_query_embedding) > p_match_threshold
        ORDER BY cm.embedding <=> p_query_embedding
        LIMIT p_limit * 3
    ),
    -- FTS 关键词检索
    fts_q AS (
        SELECT cm.id,
               ROW_NUMBER() OVER (ORDER BY ts_rank(cm.fts, plainto_tsquery('simple', p_query_text)) DESC) AS rank_pos,
               ts_rank(cm.fts, plainto_tsquery('simple', p_query_text)) AS fts_score
        FROM public.conversation_memories cm
        WHERE cm.user_id = p_user_id
          AND cm.fts @@ plainto_tsquery('simple', p_query_text)
          AND cm.superseded_by IS NULL
          AND (p_org_id IS NULL OR cm.organization_id = p_org_id)
        ORDER BY fts_score DESC
        LIMIT p_limit * 3
    ),
    -- RRF 融合 + 时间衰减 (P3)
    combined AS (
        SELECT
            COALESCE(v.id, f.id) AS mem_id,
            COALESCE(1.0 / (k + v.rank_pos), 0) + COALESCE(1.0 / (k + f.rank_pos), 0) AS rrf_score,
            COALESCE(v.vec_sim, 0) AS raw_similarity
        FROM vec v
        FULL OUTER JOIN fts_q f ON v.id = f.id
    )
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
        -- 最终得分 = RRF * importance * 时间衰减
        (c.rrf_score
         * COALESCE(cm.importance, 0.5)
         * GREATEST(0.3, 1.0 - EXTRACT(EPOCH FROM (NOW() - cm.created_at)) / (180 * 86400))
        )::FLOAT AS similarity,
        cm.version
    FROM combined c
    JOIN public.conversation_memories cm ON cm.id = c.mem_id
    ORDER BY similarity DESC
    LIMIT p_limit;
END;
$$;


-- ===== P2: chunk enriched_content 列 =====

ALTER TABLE public.document_embeddings
    ADD COLUMN IF NOT EXISTS enriched_content TEXT;


-- ===== P3: 升级原 search_memories_by_embedding 加入时间衰减 + 版本过滤 =====

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
    similarity FLOAT
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
        -- similarity * importance * time_decay
        (
            (1 - (cm.embedding <=> query_embedding))
            * COALESCE(cm.importance, 0.5)
            * GREATEST(0.3, 1.0 - EXTRACT(EPOCH FROM (NOW() - cm.created_at)) / (180 * 86400))
        )::FLOAT AS similarity
    FROM public.conversation_memories cm
    WHERE cm.user_id = match_user_id
      AND cm.embedding IS NOT NULL
      AND cm.superseded_by IS NULL  -- P0: 只检索最新版本
      AND (match_org_id IS NULL OR cm.organization_id = match_org_id)
      AND 1 - (cm.embedding <=> query_embedding) > 0.3
    ORDER BY similarity DESC
    LIMIT match_limit;
END;
$$;
