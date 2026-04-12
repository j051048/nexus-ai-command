-- ROLLBACK: 20260410_fix_kg_schema_and_rbac.sql
-- Risk: HIGH — overlaps with 20260408 migration; only rollback this migration's additions
-- NOTE: This migration uses IF NOT EXISTS, so columns may have been created by 20260408.
--       We only drop the index unique to this migration and re-create original policies.

BEGIN;

-- 1. Drop policies created by this migration
DROP POLICY IF EXISTS "Users can view and manage org graph triples" ON knowledge_graph_triples;
DROP POLICY IF EXISTS "Users can view team and org memories" ON conversation_memories;

-- 2. Drop index unique to this migration
DROP INDEX IF EXISTS idx_kg_organization_visibility;

-- 3. Re-create the original policies from 20260408 migration
-- (only if 20260408 hasn't been rolled back)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'knowledge_graph_triples') THEN
    CREATE POLICY "Users can view and manage org graph triples"
      ON knowledge_graph_triples FOR ALL
      USING (user_id = auth.uid() OR visibility IN ('team', 'organization'));
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'conversation_memories') THEN
    CREATE POLICY "Users can view team and org memories"
      ON conversation_memories FOR SELECT
      USING (user_id = auth.uid() OR visibility IN ('team', 'organization'));
  END IF;
END $$;

-- NOTE: Columns user_id, visibility, confidence on knowledge_graph_triples
-- were already defined in the CREATE TABLE of 20260408. This migration only
-- added them with IF NOT EXISTS as a safety net. Do NOT drop them here.

COMMIT;
