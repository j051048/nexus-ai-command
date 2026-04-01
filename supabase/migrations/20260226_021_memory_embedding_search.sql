-- ============================================================================
-- Migration: Add embedding column and semantic search RPC to conversation_memories
-- Date: 2026-02-26
-- Purpose: Enable pgvector semantic search on conversation_memories table.
--          Previously the table had no embedding column and the RPC function
--          search_memories_by_embedding was never created, causing silent
--          fallback to keyword search every time.
-- ============================================================================

-- 1. Ensure pgvector extension is available
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding column to conversation_memories
ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- 3. Create HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_conversation_memories_embedding
    ON public.conversation_memories
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 4. Create the RPC function for semantic memory search
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
    ORDER BY cm.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;
