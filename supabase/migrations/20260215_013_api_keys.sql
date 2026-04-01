-- ============================================================
-- 开放 API 生态 - API Keys 和使用日志表
-- ============================================================

-- API Keys 表
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,  -- 前8位，用于显示识别
    scopes TEXT[] NOT NULL DEFAULT ARRAY['read'],
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    usage_count INTEGER DEFAULT 0,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- API 使用日志表
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id),
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_api_keys_org_id ON api_keys(organization_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_api_usage_logs_key_id ON api_usage_logs(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_logs_created ON api_usage_logs(created_at DESC);

-- ============================================================
-- RLS 策略
-- ============================================================

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_usage_logs ENABLE ROW LEVEL SECURITY;

-- api_keys: 组织成员可查看本组织的 keys
CREATE POLICY "api_keys_select_org" ON api_keys
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- api_keys: 管理员可创建
CREATE POLICY "api_keys_insert_admin" ON api_keys
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('founder', 'boss')
        )
    );

-- api_keys: 管理员可更新（撤销等）
CREATE POLICY "api_keys_update_admin" ON api_keys
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM users
            WHERE id = auth.uid() AND role IN ('founder', 'boss')
        )
    );

-- api_usage_logs: 组织管理员可查看
CREATE POLICY "api_usage_logs_select_admin" ON api_usage_logs
    FOR SELECT
    USING (
        api_key_id IN (
            SELECT ak.id FROM api_keys ak
            INNER JOIN users u ON u.organization_id = ak.organization_id
            WHERE u.id = auth.uid() AND u.role IN ('founder', 'boss')
        )
    );

-- api_usage_logs: 允许插入（中间件记录使用日志）
CREATE POLICY "api_usage_logs_insert" ON api_usage_logs
    FOR INSERT
    WITH CHECK (true);

-- service key 完整访问（用于中间件验证 API Key）
CREATE POLICY "api_keys_service" ON api_keys
    FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "api_usage_logs_service" ON api_usage_logs
    FOR ALL
    USING (auth.role() = 'service_role');
