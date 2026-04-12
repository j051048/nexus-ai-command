-- ROLLBACK: 20260408_memory_rbac_and_semantic_tags.sql
-- Risk: HIGH — knowledge_graph_triples table may contain production data
-- Run with caution. Consider backing up data before executing.

BEGIN;

-- 1. Remove knowledge_graph_triples related objects (reverse order)
DROP TRIGGER IF EXISTS trg_knowledge_graph_updated_at ON knowledge_graph_triples;
DROP FUNCTION IF EXISTS update_knowledge_graph_updated_at();
DROP POLICY IF EXISTS "Users can view and manage org graph triples" ON knowledge_graph_triples;
DROP INDEX IF EXISTS idx_kg_source;
DROP INDEX IF EXISTS idx_kg_destination;
DROP INDEX IF EXISTS idx_kg_relationship;
-- WARNING: This will permanently delete all knowledge graph data
DROP TABLE IF EXISTS knowledge_graph_triples;

-- 2. Revert conversation_memories changes
DROP POLICY IF EXISTS "Users can view team and org memories" ON conversation_memories;
DROP INDEX IF EXISTS idx_conversation_memories_semantic_tags;
ALTER TABLE conversation_memories DROP COLUMN IF EXISTS semantic_tags;
ALTER TABLE conversation_memories DROP COLUMN IF EXISTS visibility;

COMMIT;
