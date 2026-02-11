-- AI-First 企业平台增强迁移
-- 版本: 20250211
-- 增强内容: 审计日志不可变性、缓存增量更新 RPC

-- ============================================
-- 1. 审计日志不可变性保护
-- ============================================

-- 创建触发器函数：阻止 audit_logs 的更新和删除
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '审计日志不可修改或删除 (Audit logs are immutable)';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 添加触发器（如果不存在）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'prevent_audit_modification'
        AND tgrelid = 'audit_logs'::regclass
    ) THEN
        CREATE TRIGGER prevent_audit_modification
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    END IF;
EXCEPTION WHEN undefined_table THEN
    -- audit_logs 表不存在，跳过
    NULL;
END $$;

-- ============================================
-- 2. 语义缓存命中计数原子更新 RPC
-- ============================================

CREATE OR REPLACE FUNCTION increment_cache_hit(p_cache_id INTEGER)
RETURNS void AS $$
BEGIN
    UPDATE semantic_cache
    SET
        hit_count = hit_count + 1,
        last_hit_at = NOW()
    WHERE id = p_cache_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- 3. 关键词搜索 RPC（支持三层可见性模型）
-- ============================================

CREATE OR REPLACE FUNCTION match_documents_keyword(
    p_query TEXT,
    p_user_id UUID,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    doc_metadata JSONB,
    visibility TEXT,
    score REAL
) AS $$
DECLARE
    v_user_dept TEXT;
    v_user_org UUID;
BEGIN
    -- 获取用户部门和组织
    SELECT department, organization_id INTO v_user_dept, v_user_org
    FROM users WHERE id = p_user_id;

    RETURN QUERY
    SELECT
        de.id,
        de.content,
        de.metadata,
        d.metadata as doc_metadata,
        d.visibility,
        ts_rank(de.fts, plainto_tsquery('simple', p_query)) as score
    FROM document_embeddings de
    JOIN documents d ON de.document_id = d.id
    WHERE
        de.fts @@ plainto_tsquery('simple', p_query)
        AND (
            d.visibility = 'organization'
            OR (d.visibility = 'department' AND d.department = v_user_dept)
            OR d.owner_id = p_user_id
        )
    ORDER BY score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- 4. Agent 思考链记录表
-- ============================================

CREATE TABLE IF NOT EXISTS agent_thinking_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    message_id VARCHAR(100),
    thinking_steps JSONB DEFAULT '[]',
    tool_calls JSONB DEFAULT '[]',
    total_duration_ms INTEGER,
    model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_agent_thinking_session ON agent_thinking_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_thinking_user ON agent_thinking_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_thinking_created ON agent_thinking_logs(created_at DESC);

-- ============================================
-- 5. RLS 策略增强
-- ============================================

-- 确保 semantic_cache 有 RLS
ALTER TABLE semantic_cache ENABLE ROW LEVEL SECURITY;

-- 语义缓存读取策略（用户只能读取自己的缓存或组织级缓存）
DROP POLICY IF EXISTS semantic_cache_select_policy ON semantic_cache;
CREATE POLICY semantic_cache_select_policy ON semantic_cache
    FOR SELECT USING (
        user_id = auth.uid()
        OR org_id IN (SELECT organization_id FROM users WHERE id = auth.uid())
    );

-- 语义缓存插入策略
DROP POLICY IF EXISTS semantic_cache_insert_policy ON semantic_cache;
CREATE POLICY semantic_cache_insert_policy ON semantic_cache
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Agent 思考链日志策略
ALTER TABLE agent_thinking_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_thinking_select_policy ON agent_thinking_logs;
CREATE POLICY agent_thinking_select_policy ON agent_thinking_logs
    FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS agent_thinking_insert_policy ON agent_thinking_logs;
CREATE POLICY agent_thinking_insert_policy ON agent_thinking_logs
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- ============================================
-- 6. 性能优化索引
-- ============================================

-- 语义缓存查询优化
CREATE INDEX IF NOT EXISTS idx_semantic_cache_user_org ON semantic_cache(user_id, org_id);
CREATE INDEX IF NOT EXISTS idx_semantic_cache_hit_count ON semantic_cache(hit_count DESC);

-- 文档嵌入查询优化
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_doc_id ON document_embeddings(document_id);

COMMENT ON TABLE agent_thinking_logs IS 'Agent 思考链执行日志，用于可观测性和调试';
