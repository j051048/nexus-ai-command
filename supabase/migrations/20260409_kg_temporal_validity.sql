-- Add temporal validity window to knowledge graph triples
-- Enables time-travel queries like "Where was 张三 working last year?"

-- valid_from: when this fact became true (backfilled from created_at)
ALTER TABLE knowledge_graph_triples
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ DEFAULT NOW();

-- Backfill: existing rows get valid_from = created_at
UPDATE knowledge_graph_triples
    SET valid_from = created_at
    WHERE valid_from IS NULL;

-- Composite index for temporal range queries
CREATE INDEX IF NOT EXISTS idx_kg_temporal
    ON knowledge_graph_triples(organization_id, source_entity, valid_from, valid_to);
