-- P1 学习能力 + P2 性能优化

-- P1-1: 错误学习表
CREATE TABLE IF NOT EXISTS agent_failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name TEXT NOT NULL,
    error_pattern TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    user_id UUID NOT NULL,
    org_id TEXT DEFAULT 'default',
    frequency INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_successes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name TEXT NOT NULL,
    solution TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    org_id TEXT DEFAULT 'default',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- P1-2: 用户偏好表
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    org_id TEXT DEFAULT 'default',
    preference_type TEXT NOT NULL,
    preference_data JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, preference_type)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_failures_tool ON agent_failures(tool_name, org_id);
CREATE INDEX IF NOT EXISTS idx_successes_tool ON agent_successes(tool_name, org_id);
CREATE INDEX IF NOT EXISTS idx_preferences_user ON user_preferences(user_id, org_id);
