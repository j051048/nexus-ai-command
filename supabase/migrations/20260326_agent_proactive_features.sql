-- P0 主动性改造：后台调度、目标追踪、事件触发

-- 1. 定时任务表
CREATE TABLE IF NOT EXISTS agent_scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    prompt_template TEXT NOT NULL,
    user_id UUID NOT NULL,
    org_id TEXT DEFAULT 'default',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 任务执行历史
CREATE TABLE IF NOT EXISTS agent_task_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES agent_scheduled_tasks(id) ON DELETE CASCADE,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    result_summary TEXT,
    error_message TEXT
);

-- 3. 长期目标表
CREATE TABLE IF NOT EXISTS agent_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    org_id TEXT DEFAULT 'default',
    goal_text TEXT NOT NULL,
    deadline TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    progress JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_enabled ON agent_scheduled_tasks(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_task_executions_task_id ON agent_task_executions(task_id);
CREATE INDEX IF NOT EXISTS idx_goals_user_status ON agent_goals(user_id, status);
CREATE INDEX IF NOT EXISTS idx_goals_deadline ON agent_goals(deadline) WHERE status IN ('pending', 'in_progress');

-- 更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_scheduled_tasks_updated_at
    BEFORE UPDATE ON agent_scheduled_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_goals_updated_at
    BEFORE UPDATE ON agent_goals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
