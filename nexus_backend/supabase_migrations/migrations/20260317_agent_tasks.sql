-- P1a: External Task System for Agent
-- Provides persistent task tracking independent of conversation context.
-- Agent can create/update/list tasks to maintain direction across context compressions.

CREATE TABLE IF NOT EXISTS agent_tasks (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id text NOT NULL,
    tenant_id       text,
    user_id         text NOT NULL,
    title           text NOT NULL,
    description     text DEFAULT '',
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'in_progress', 'done', 'blocked')),
    depends_on      jsonb DEFAULT '[]'::jsonb,
    context_summary text DEFAULT '',
    sort_order      int DEFAULT 0,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_agent_tasks_user_session
    ON agent_tasks (user_id, conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_tenant
    ON agent_tasks (tenant_id) WHERE tenant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status
    ON agent_tasks (status) WHERE status != 'done';

-- RLS
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;

-- Users can only see their own tasks
CREATE POLICY agent_tasks_user_policy ON agent_tasks
    FOR ALL
    USING (user_id = auth.uid()::text)
    WITH CHECK (user_id = auth.uid()::text);

-- AI assistant service role has full access
CREATE POLICY agent_tasks_service_policy ON agent_tasks
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_agent_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_tasks_updated_at ON agent_tasks;
CREATE TRIGGER trg_agent_tasks_updated_at
    BEFORE UPDATE ON agent_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_tasks_updated_at();
