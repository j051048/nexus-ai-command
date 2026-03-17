-- ============================================================================
-- Migration: Knowledge Graph Provenance + Temporal Lifecycle + FTS
--
-- 方案2: Episodic provenance — link triples back to their source conversation
-- 方案3: Temporal lifecycle — soft-expire instead of overwrite (valid_from/valid_to)
-- 方案1: FTS hybrid search — tsvector + GIN index for keyword retrieval
-- ============================================================================

-- ===== 方案2: 情景追溯化 =====
ALTER TABLE public.knowledge_graph_triples
    ADD COLUMN IF NOT EXISTS source_session_id TEXT,
    ADD COLUMN IF NOT EXISTS source_message_id UUID;

COMMENT ON COLUMN public.knowledge_graph_triples.source_session_id IS '对话会话 ID，追溯三元组的原始来源';
COMMENT ON COLUMN public.knowledge_graph_triples.source_message_id IS '消息 ID，追溯三元组的精确来源';

CREATE INDEX IF NOT EXISTS idx_kg_source_session
    ON public.knowledge_graph_triples (source_session_id)
    WHERE source_session_id IS NOT NULL;

-- ===== 方案3: 时效生命线 =====
ALTER TABLE public.knowledge_graph_triples
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;

COMMENT ON COLUMN public.knowledge_graph_triples.valid_from IS '事实生效时间';
COMMENT ON COLUMN public.knowledge_graph_triples.valid_to IS '事实失效时间（NULL=当前有效）';

-- 查询当前有效三元组时可用的局部索引
CREATE INDEX IF NOT EXISTS idx_kg_active_triples
    ON public.knowledge_graph_triples (organization_id, source_entity)
    WHERE valid_to IS NULL;

-- ===== 方案1简化版: FTS 混合检索 =====
-- 给三元组表加 tsvector 列用于关键词检索
ALTER TABLE public.knowledge_graph_triples
    ADD COLUMN IF NOT EXISTS fts tsvector;

-- 基于实体名 + 关系 + 上下文生成 tsvector
UPDATE public.knowledge_graph_triples
SET fts = to_tsvector('simple',
    COALESCE(source_entity, '') || ' ' ||
    COALESCE(relationship, '') || ' ' ||
    COALESCE(destination_entity, '') || ' ' ||
    COALESCE(source_context, '')
)
WHERE fts IS NULL;

CREATE INDEX IF NOT EXISTS idx_kg_fts
    ON public.knowledge_graph_triples USING GIN (fts);

-- 自动维护 fts 列的触发器
CREATE OR REPLACE FUNCTION kg_triples_fts_trigger()
RETURNS trigger
LANGUAGE plpgsql AS $$
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
    FOR EACH ROW EXECUTE FUNCTION kg_triples_fts_trigger();


-- ===== 混合检索 RPC: 向量 + FTS + RRF 融合 =====
-- 搜索知识图谱三元组，支持向量语义 + 关键词双路召回
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
          AND t.valid_to IS NULL  -- 只搜索当前有效的三元组
          AND t.fts @@ plainto_tsquery('simple', p_query_text)
        ORDER BY fts_score DESC
        LIMIT p_limit * 3
    ),
    -- 精确实体名匹配（ILIKE 兜底，防止分词遗漏专有名词）
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
