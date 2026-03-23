-- Migration: Entity resolution aliases + KG decay support
-- Supports: entity merging, multi-hop traversal, strength decay

-- ============================================================================
-- 1. Entity Aliases — canonical name mapping for entity resolution
-- ============================================================================
CREATE TABLE IF NOT EXISTS entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    alias VARCHAR(200) NOT NULL,
    canonical_name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50) DEFAULT 'concept',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_alias_unique
    ON entity_aliases(organization_id, alias);
CREATE INDEX IF NOT EXISTS idx_entity_alias_canonical
    ON entity_aliases(organization_id, canonical_name);

-- RLS
ALTER TABLE entity_aliases ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their org entity aliases"
    ON entity_aliases FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

CREATE POLICY "Users can insert entity aliases for their org"
    ON entity_aliases FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

CREATE POLICY "Users can update entity aliases for their org"
    ON entity_aliases FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

-- ============================================================================
-- 2. Add embedding column to knowledge_graph_triples for entity similarity
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'knowledge_graph_triples' AND column_name = 'source_embedding'
    ) THEN
        ALTER TABLE knowledge_graph_triples
            ADD COLUMN source_embedding vector(1536),
            ADD COLUMN dest_embedding vector(1536);
    END IF;
END $$;

-- ============================================================================
-- 3. Add last_reinforced_at for decay tracking (distinct from updated_at)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'knowledge_graph_triples' AND column_name = 'last_reinforced_at'
    ) THEN
        ALTER TABLE knowledge_graph_triples
            ADD COLUMN last_reinforced_at TIMESTAMPTZ DEFAULT NOW();
        -- Backfill existing rows
        UPDATE knowledge_graph_triples
            SET last_reinforced_at = COALESCE(updated_at, created_at)
            WHERE last_reinforced_at IS NULL;
    END IF;
END $$;

-- ============================================================================
-- 4. Ensure valid_to and source_session_id columns exist (used in code)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'knowledge_graph_triples' AND column_name = 'valid_to'
    ) THEN
        ALTER TABLE knowledge_graph_triples ADD COLUMN valid_to TIMESTAMPTZ;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'knowledge_graph_triples' AND column_name = 'source_session_id'
    ) THEN
        ALTER TABLE knowledge_graph_triples ADD COLUMN source_session_id TEXT;
    END IF;
END $$;

-- ============================================================================
-- 5. RPC: find similar entities by embedding cosine distance
-- ============================================================================
CREATE OR REPLACE FUNCTION find_similar_entities(
    p_org_id UUID,
    p_embedding vector(1536),
    p_threshold FLOAT DEFAULT 0.15,
    p_limit INT DEFAULT 5
)
RETURNS TABLE (
    entity_name VARCHAR(200),
    entity_type VARCHAR(50),
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    -- Search source entities
    SELECT DISTINCT ON (source_entity)
        source_entity AS entity_name,
        source_type AS entity_type,
        1 - (source_embedding <=> p_embedding) AS similarity
    FROM knowledge_graph_triples
    WHERE organization_id = p_org_id
        AND source_embedding IS NOT NULL
        AND valid_to IS NULL
        AND 1 - (source_embedding <=> p_embedding) > p_threshold
    UNION
    SELECT DISTINCT ON (destination_entity)
        destination_entity AS entity_name,
        destination_type AS entity_type,
        1 - (dest_embedding <=> p_embedding) AS similarity
    FROM knowledge_graph_triples
    WHERE organization_id = p_org_id
        AND dest_embedding IS NOT NULL
        AND valid_to IS NULL
        AND 1 - (dest_embedding <=> p_embedding) > p_threshold
    ORDER BY similarity DESC
    LIMIT p_limit;
$$;

-- ============================================================================
-- 6. RPC: 2-hop graph traversal
-- ============================================================================
CREATE OR REPLACE FUNCTION query_entity_relations_2hop(
    p_org_id UUID,
    p_entity_name VARCHAR(200),
    p_limit INT DEFAULT 30
)
RETURNS TABLE (
    id UUID,
    source_entity VARCHAR(200),
    source_type VARCHAR(50),
    relationship VARCHAR(100),
    destination_entity VARCHAR(200),
    destination_type VARCHAR(50),
    strength FLOAT,
    hop INT
)
LANGUAGE sql STABLE
AS $$
    -- Hop 1: direct relations
    WITH hop1 AS (
        SELECT t.id, t.source_entity, t.source_type, t.relationship,
               t.destination_entity, t.destination_type, t.strength,
               1 AS hop
        FROM knowledge_graph_triples t
        WHERE t.organization_id = p_org_id
          AND t.valid_to IS NULL
          AND (t.source_entity = p_entity_name OR t.destination_entity = p_entity_name)
        ORDER BY t.strength DESC
        LIMIT p_limit
    ),
    -- Collect neighbor entity names from hop1
    neighbors AS (
        SELECT DISTINCT
            CASE WHEN source_entity = p_entity_name THEN destination_entity
                 ELSE source_entity END AS neighbor
        FROM hop1
    ),
    -- Hop 2: relations of neighbors (excluding original entity to avoid loops)
    hop2 AS (
        SELECT t.id, t.source_entity, t.source_type, t.relationship,
               t.destination_entity, t.destination_type, t.strength * 0.6 AS strength,
               2 AS hop
        FROM knowledge_graph_triples t
        INNER JOIN neighbors n
            ON (t.source_entity = n.neighbor OR t.destination_entity = n.neighbor)
        WHERE t.organization_id = p_org_id
          AND t.valid_to IS NULL
          AND t.source_entity != p_entity_name
          AND t.destination_entity != p_entity_name
          AND t.id NOT IN (SELECT h.id FROM hop1 h)
        ORDER BY t.strength DESC
        LIMIT p_limit
    )
    SELECT * FROM hop1
    UNION ALL
    SELECT * FROM hop2
    ORDER BY hop ASC, strength DESC
    LIMIT p_limit;
$$;
