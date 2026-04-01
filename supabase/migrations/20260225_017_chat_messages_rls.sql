-- ============================================================================
-- Migration: Add organization_id to chat_messages for tenant isolation
-- Date: 2026-02-25
-- Purpose: Fix security red line — chat_messages had no org-level RLS
-- ============================================================================
-- 1. Add organization_id column (nullable for backward compat with existing rows)
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES organizations(id);
-- 2. Backfill organization_id from users table for existing rows
UPDATE chat_messages cm
SET organization_id = u.organization_id
FROM users u
WHERE cm.user_id = u.id
  AND cm.organization_id IS NULL;
-- 3. Create index for tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_org_id ON chat_messages(organization_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_org_user_session ON chat_messages(organization_id, user_id, session_id);
-- 4. Enable RLS
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
-- 5. Drop existing policies if any (idempotent)
DROP POLICY IF EXISTS "chat_messages_select_own" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_delete_own" ON chat_messages;
-- 6. RLS policies - users can read/delete their own messages
CREATE POLICY "chat_messages_select_own" ON chat_messages FOR
SELECT USING (user_id = auth.uid());
CREATE POLICY "chat_messages_delete_own" ON chat_messages FOR DELETE USING (user_id = auth.uid());
-- 7. Service role can always write (backend uses admin client for inserts)
GRANT ALL ON chat_messages TO service_role;