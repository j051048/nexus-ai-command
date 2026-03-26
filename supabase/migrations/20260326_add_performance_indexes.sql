-- Performance optimization: Add indexes for frequently queried columns
-- Created: 2026-03-26

-- Chat messages indexes
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_session
ON chat_messages(user_id, session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_messages_content_search
ON chat_messages USING gin(to_tsvector('english', content));

-- AI settings index
CREATE INDEX IF NOT EXISTS idx_ai_settings_user_org
ON ai_settings(user_id, organization_id);

-- System configs index
CREATE INDEX IF NOT EXISTS idx_system_configs_org_type
ON system_configs(organization_id, config_type, is_active);

-- Users profile index
CREATE INDEX IF NOT EXISTS idx_users_org_role
ON users(organization_id, role);

-- Approval requests index
CREATE INDEX IF NOT EXISTS idx_approval_requests_status
ON approval_requests(organization_id, status, created_at DESC);
