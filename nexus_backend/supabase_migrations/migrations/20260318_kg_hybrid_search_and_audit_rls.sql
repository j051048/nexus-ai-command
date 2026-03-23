-- ============================================================================
-- 1. search_kg_triples_hybrid RPC 函数
--    FTS + ILIKE 混合搜索知识图谱三元组
-- ============================================================================

-- 确保 knowledge_graph_triples 表有 fts 列和相关基础设施
DO $$
BEGIN
    -- 添加 fts 列（如果不存在）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'knowledge_graph_triples'
          AND column_name = 'fts'
    ) THEN
        ALTER TABLE public.knowledge_graph_triples
            ADD COLUMN fts tsvector;
    END IF;

    -- 添加 valid_from 列（如果不存在）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'knowledge_graph_triples'
          AND column_name = 'valid_from'
    ) THEN
        ALTER TABLE public.knowledge_graph_triples
            ADD COLUMN valid_from TIMESTAMPTZ DEFAULT NOW();
    END IF;

    -- 添加 source_session_id 列（如果不存在）
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'knowledge_graph_triples'
          AND column_name = 'source_session_id'
    ) THEN
        ALTER TABLE public.knowledge_graph_triples
            ADD COLUMN source_session_id TEXT;
    END IF;
END $$;

-- fts GIN 索引
CREATE INDEX IF NOT EXISTS idx_kg_triples_fts
    ON public.knowledge_graph_triples USING gin(fts);

-- 自动维护 fts 列的触发器
CREATE OR REPLACE FUNCTION public.kg_triples_fts_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.fts := to_tsvector('simple',
        COALESCE(NEW.source_entity, '') || ' ' ||
        COALESCE(NEW.relationship, '') || ' ' ||
        COALESCE(NEW.destination_entity, '') || ' ' ||
        COALESCE(NEW.source_context, '')
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_kg_triples_fts ON public.knowledge_graph_triples;
CREATE TRIGGER trg_kg_triples_fts
    BEFORE INSERT OR UPDATE ON public.knowledge_graph_triples
    FOR EACH ROW EXECUTE FUNCTION public.kg_triples_fts_update();

-- 回填已有行的 fts
UPDATE public.knowledge_graph_triples
SET fts = to_tsvector('simple',
    COALESCE(source_entity, '') || ' ' ||
    COALESCE(relationship, '') || ' ' ||
    COALESCE(destination_entity, '') || ' ' ||
    COALESCE(source_context, '')
)
WHERE fts IS NULL;

-- RPC 函数
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
DECLARE
    k CONSTANT INT := 60;  -- RRF constant
BEGIN
    RETURN QUERY
    WITH
    -- FTS 关键词检索
    fts_results AS (
        SELECT
            t.id,
            ROW_NUMBER() OVER (ORDER BY ts_rank(t.fts, plainto_tsquery('simple', p_query_text)) DESC) AS rank_pos,
            ts_rank(t.fts, plainto_tsquery('simple', p_query_text)) AS fts_score
        FROM public.knowledge_graph_triples t
        WHERE t.organization_id = p_org_id
          AND t.valid_to IS NULL
          AND t.fts @@ plainto_tsquery('simple', p_query_text)
        ORDER BY fts_score DESC
        LIMIT p_limit * 3
    ),
    -- 精确实体名匹配
    entity_match AS (
        SELECT
            t.id,
            ROW_NUMBER() OVER (ORDER BY t.strength DESC, t.occurrences DESC) AS rank_pos
        FROM public.knowledge_graph_triples t
        WHERE t.organization_id = p_org_id
          AND t.valid_to IS NULL
          AND (
              t.source_entity ILIKE '%' || p_query_text || '%'
              OR t.destination_entity ILIKE '%' || p_query_text || '%'
              OR t.relationship ILIKE '%' || p_query_text || '%'
          )
        ORDER BY t.strength DESC, t.occurrences DESC
        LIMIT p_limit * 2
    ),
    -- RRF 融合
    combined AS (
        SELECT
            COALESCE(f.id, e.id) AS triple_id,
            COALESCE(1.0 / (k + f.rank_pos), 0) + COALESCE(1.0 / (k + e.rank_pos), 0) AS rrf_score
        FROM fts_results f
        FULL OUTER JOIN entity_match e ON f.id = e.id
    )
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
        (c.rrf_score * COALESCE(t.strength, 0.5))::FLOAT AS score
    FROM combined c
    JOIN public.knowledge_graph_triples t ON t.id = c.triple_id
    ORDER BY score DESC
    LIMIT p_limit;
END;
$$;

-- ============================================================================
-- 2. memory_audit_log RLS — 补充 INSERT 策略
--    后端 service_role 和用户自身都可以写入审计日志
-- ============================================================================

-- 确保 RLS 已启用
ALTER TABLE public.memory_audit_log ENABLE ROW LEVEL SECURITY;

-- INSERT 策略：用户可以为自己写审计日志
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'memory_audit_log'
          AND policyname = 'Users can insert their own audit logs'
    ) THEN
        CREATE POLICY "Users can insert their own audit logs"
            ON public.memory_audit_log
            FOR INSERT
            WITH CHECK (auth.uid() = user_id);
    END IF;
END $$;

-- service_role 全权访问（绕过 RLS），但显式策略确保 anon/authenticated 也能写
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'memory_audit_log'
          AND policyname = 'Service role full access to audit logs'
    ) THEN
        CREATE POLICY "Service role full access to audit logs"
            ON public.memory_audit_log
            FOR ALL
            USING (auth.role() = 'service_role')
            WITH CHECK (auth.role() = 'service_role');
    END IF;
END $$;
