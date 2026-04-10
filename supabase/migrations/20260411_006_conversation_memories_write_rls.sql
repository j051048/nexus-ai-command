-- Migration: Add INSERT/UPDATE/DELETE RLS policies for conversation_memories
-- Date: 2026-04-11
-- Purpose: Fix "new row violates row-level security policy" on INSERT
-- Root cause: 20260410_fix_rls_org_isolation.sql only created a SELECT policy,
--   dropping the old FOR ALL policy without replacing write policies.

-- Drop the old FOR ALL policy (may or may not still exist)
DROP POLICY IF EXISTS "Users manage own memories" ON conversation_memories;

-- INSERT: users can insert memories into their own org
CREATE POLICY "memories_insert_policy"
    ON conversation_memories
    FOR INSERT
    WITH CHECK (
        organization_id = public.get_user_org_id(auth.uid())
        AND user_id = auth.uid()
    );

-- UPDATE: owner or managers within the same org can update
CREATE POLICY "memories_update_policy"
    ON conversation_memories
    FOR UPDATE
    USING (
        organization_id = public.get_user_org_id(auth.uid())
        AND (
            user_id = auth.uid()
            OR EXISTS (
                SELECT 1 FROM public.organization_members
                WHERE organization_id = public.get_user_org_id(auth.uid())
                  AND user_id = auth.uid()
                  AND role IN ('manager', 'boss', 'founder')
            )
        )
    );

-- DELETE: owner or managers within the same org can delete
CREATE POLICY "memories_delete_policy"
    ON conversation_memories
    FOR DELETE
    USING (
        organization_id = public.get_user_org_id(auth.uid())
        AND (
            user_id = auth.uid()
            OR EXISTS (
                SELECT 1 FROM public.organization_members
                WHERE organization_id = public.get_user_org_id(auth.uid())
                  AND user_id = auth.uid()
                  AND role IN ('manager', 'boss', 'founder')
            )
        )
    );
