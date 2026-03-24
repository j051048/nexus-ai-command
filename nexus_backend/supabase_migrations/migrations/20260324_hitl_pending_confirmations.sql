-- HITL: Persist blocked tool confirmations for async approval
-- Allows users to approve/reject tool executions even after disconnecting

CREATE TABLE IF NOT EXISTS pending_confirmations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    session_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_args JSONB NOT NULL DEFAULT '{}',
    tool_call_id TEXT NOT NULL,
    confirmation_type TEXT NOT NULL DEFAULT '',  -- irreversible | high_value | bulk
    message TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    resolved_by UUID REFERENCES auth.users(id),
    resolved_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pending_confirmations_user_status
    ON pending_confirmations(user_id, status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_pending_confirmations_org
    ON pending_confirmations(organization_id);
CREATE INDEX IF NOT EXISTS idx_pending_confirmations_expires
    ON pending_confirmations(expires_at) WHERE status = 'pending';

-- RLS
ALTER TABLE pending_confirmations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own confirmations"
    ON pending_confirmations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own confirmations"
    ON pending_confirmations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Service role full access"
    ON pending_confirmations FOR ALL
    USING (auth.role() = 'service_role');
