-- Migration: Fix RLS policies - add org_id isolation and split FOR ALL into granular policies
-- Date: 2026-04-09
--
-- Fixes:
--   1. [P0] RLS policies lacked organization_id filter → cross-tenant data leakage
--   2. [P1] FOR ALL policy on knowledge_graph_triples was too permissive for writes

-- ── knowledge_graph_triples ──

-- Drop the overly broad FOR ALL policy
DROP POLICY IF EXISTS "Users can view and manage org graph triples" ON knowledge_graph_triples;

-- SELECT: users can see their own triples OR team/org-visible triples within their org
CREATE POLICY "kg_select_policy"
    ON knowledge_graph_triples
    FOR SELECT
    USING (
        organization_id = public.get_user_org_id(auth.uid())
        AND (user_id = auth.uid() OR visibility IN ('team', 'organization'))
    );

-- INSERT: users can only insert into their own org
CREATE POLICY "kg_insert_policy"
    ON knowledge_graph_triples
    FOR INSERT
    WITH CHECK (
        organization_id = public.get_user_org_id(auth.uid())
    );

-- UPDATE: only the owner or managers within the same org can update
CREATE POLICY "kg_update_policy"
    ON knowledge_graph_triples
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

-- DELETE: only the owner or managers within the same org can delete
CREATE POLICY "kg_delete_policy"
    ON knowledge_graph_triples
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

-- ── conversation_memories ──

-- Drop the old policy that lacked org isolation
DROP POLICY IF EXISTS "Users can view team and org memories" ON conversation_memories;

-- SELECT: users can see their own memories OR team/org-visible memories within their org
CREATE POLICY "memories_select_policy"
    ON conversation_memories
    FOR SELECT
    USING (
        organization_id = public.get_user_org_id(auth.uid())
        AND (user_id = auth.uid() OR visibility IN ('team', 'organization'))
    );
