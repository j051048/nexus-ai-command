-- Agent failure logs for tracking and learning from AI errors
CREATE TABLE IF NOT EXISTS agent_failure_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    conversation_id UUID,
    user_message TEXT NOT NULL,
    intent_summary TEXT,
    complexity TEXT,
    tool_calls JSONB DEFAULT '[]',
    error_type TEXT NOT NULL CHECK (error_type IN (
        'wrong_tool', 'wrong_params', 'hallucination',
        'timeout', 'permission', 'loop', 'empty_response', 'unknown'
    )),
    error_detail TEXT,
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_failure_logs_org ON agent_failure_logs(organization_id, created_at DESC);
CREATE INDEX idx_failure_logs_type ON agent_failure_logs(error_type);

ALTER TABLE agent_failure_logs ENABLE ROW LEVEL SECURITY;

-- RLS: org members can view their org's failure logs
CREATE POLICY "org_members_view_failure_logs" ON agent_failure_logs
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );
