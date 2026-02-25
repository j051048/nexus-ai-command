-- ============================================================================
-- Migration: Add organization_id to chat_messages for tenant isolation
-- Date: 2026-02-25
-- Purpose: Fix security red line — chat_messages had no org-level RLS
-- ============================================================================

-- 1. Add organization_id column (nullable for backward compat with existing rows)
ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id);

-- 2. Add agent column (was missing despite being queried in code)
ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS agent text;

-- 3. Backfill organization_id from users table for existing rows
UPDATE chat_messages cm
SET organization_id = u.organization_id
FROM users u
WHERE cm.user_id = u.id::text
  AND cm.organization_id IS NULL;

-- 4. Create index for tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_org_id
  ON chat_messages(organization_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_org_user_session
  ON chat_messages(organization_id, user_id, session_id);

-- 5. Enable RLS
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- 6. RLS policies
-- Users can read/delete their own messages within their organization
CREATE POLICY "chat_messages_select_own"
  ON chat_messages FOR SELECT
  USING (user_id = auth.uid()::text);

CREATE POLICY "chat_messages_delete_own"
  ON chat_messages FOR DELETE
  USING (user_id = auth.uid()::text);

-- INSERT/UPDATE uses service key (bypasses RLS), so no INSERT policy needed
-- for authenticated users. The backend always uses the admin client for writes.
-- This GRANT ensures the service role can always write.
GRANT ALL ON chat_messages TO service_role;
