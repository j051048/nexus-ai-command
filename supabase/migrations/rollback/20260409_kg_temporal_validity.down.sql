-- ROLLBACK: 20260409_kg_temporal_validity.sql
-- Risk: MEDIUM — valid_from was backfilled from created_at, data will be lost

BEGIN;

DROP INDEX IF EXISTS idx_kg_temporal;
ALTER TABLE knowledge_graph_triples DROP COLUMN IF EXISTS valid_to;
ALTER TABLE knowledge_graph_triples DROP COLUMN IF EXISTS valid_from;

COMMIT;
