-- ============================================================================
-- Migration 018: Strengthen chat_messages RLS with organization-level isolation
-- Date: 2026-02-26
-- Purpose: Add org_id check to RLS policies so isolation is enforced at SQL level,
--          not just at the application layer (scoped client).
-- ============================================================================

-- 1. Drop existing policies
DROP POLICY IF EXISTS "chat_messages_select_own" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_delete_own" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_insert_own" ON chat_messages;

-- 2. Recreate with dual isolation: user_id + organization_id
-- SELECT: user can only read their own messages within their organization
CREATE POLICY "chat_messages_select_own" ON chat_messages
  FOR SELECT USING (
    user_id = auth.uid()
    AND organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- DELETE: user can only delete their own messages within their organization
CREATE POLICY "chat_messages_delete_own" ON chat_messages
  FOR DELETE USING (
    user_id = auth.uid()
    AND organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- INSERT: user can only insert messages for themselves within their organization
CREATE POLICY "chat_messages_insert_own" ON chat_messages
  FOR INSERT WITH CHECK (
    user_id = auth.uid()
    AND organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 3. Service role retains full access (backend admin operations)
GRANT ALL ON chat_messages TO service_role;
