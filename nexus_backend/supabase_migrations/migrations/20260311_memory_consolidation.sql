-- ============================================================================
-- Migration: Memory Consolidation System
-- Date: 2026-03-11
-- Purpose: 借鉴 Google Always-On Memory Agent，为记忆系统增加三项能力：
--   1. 记忆整合 (Sleep Cycle) — 定时合并相关记忆、发现模式
--   2. 重要性动态调优 — search_memories_by_embedding 按 similarity*importance 排序
--   3. 记忆关系图 — connections 字段记录记忆间关联
-- ============================================================================

-- 1. 新表: memory_consolidations — 存储整合后的跨记忆洞察
CREATE TABLE IF NOT EXISTS public.memory_consolidations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID,
    insight_type TEXT NOT NULL DEFAULT 'pattern',  -- pattern / summary / contradiction
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_memory_ids UUID[] NOT NULL DEFAULT '{}',
    importance FLOAT NOT NULL DEFAULT 0.6,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_consolidations_user
    ON public.memory_consolidations(user_id);

CREATE INDEX IF NOT EXISTS idx_memory_consolidations_embedding
    ON public.memory_consolidations
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- RLS
ALTER TABLE public.memory_consolidations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_consolidations" ON public.memory_consolidations
    FOR ALL USING (auth.uid() = user_id);


-- 2. conversation_memories 新增列
ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS is_consolidated BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS connections JSONB NOT NULL DEFAULT '[]'::jsonb;
-- connections 格式: [{"memory_id": "uuid", "relation": "supplements", "strength": 0.8}]
-- relation 枚举: same_customer, same_project, causal, contradicts, supplements


-- 3. RPC: search_consolidations_by_embedding
CREATE OR REPLACE FUNCTION public.search_consolidations_by_embedding(
    query_embedding vector(1536),
    match_user_id UUID,
    match_limit INT DEFAULT 3,
    match_org_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    organization_id UUID,
    insight_type TEXT,
    title TEXT,
    content TEXT,
    source_memory_ids UUID[],
    importance FLOAT,
    created_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        mc.id,
        mc.user_id,
        mc.organization_id,
        mc.insight_type,
        mc.title,
        mc.content,
        mc.source_memory_ids,
        mc.importance,
        mc.created_at,
        1 - (mc.embedding <=> query_embedding) AS similarity
    FROM public.memory_consolidations mc
    WHERE mc.user_id = match_user_id
      AND mc.embedding IS NOT NULL
      AND (match_org_id IS NULL OR mc.organization_id = match_org_id)
      AND 1 - (mc.embedding <=> query_embedding) > 0.3
    ORDER BY mc.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;


-- 4. 升级 search_memories_by_embedding: 按 similarity * importance 联合排序
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
        1 - (cm.embedding <=> query_embedding) AS similarity
    FROM public.conversation_memories cm
    WHERE cm.user_id = match_user_id
      AND cm.embedding IS NOT NULL
      AND (match_org_id IS NULL OR cm.organization_id = match_org_id)
      AND 1 - (cm.embedding <=> query_embedding) > 0.3
    ORDER BY (1 - (cm.embedding <=> query_embedding)) * COALESCE(cm.importance, 0.5) DESC
    LIMIT match_limit;
END;
$$;
