-- Migration: Add memory audit log + knowledge graph triples tables
-- Part of the Mem0-inspired memory system optimization

-- ============================================================================
-- 1. Memory Audit Log — tracks every ADD / UPDATE / DELETE on memories
-- ============================================================================
CREATE TABLE IF NOT EXISTS memory_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL,
    user_id UUID NOT NULL,
    action VARCHAR(10) NOT NULL CHECK (action IN ('ADD', 'UPDATE', 'DELETE')),
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    actor VARCHAR(50) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_memory_id
    ON memory_audit_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_audit_user_created
    ON memory_audit_log(user_id, created_at DESC);

-- RLS
ALTER TABLE memory_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own audit logs"
    ON memory_audit_log FOR SELECT
    USING (auth.uid() = user_id);

-- ============================================================================
-- 2. Knowledge Graph Triples — lightweight graph storage in PostgreSQL
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_graph_triples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    source_entity VARCHAR(200) NOT NULL,
    source_type VARCHAR(50) NOT NULL DEFAULT 'concept',
    relationship VARCHAR(100) NOT NULL,
    destination_entity VARCHAR(200) NOT NULL,
    destination_type VARCHAR(50) NOT NULL DEFAULT 'concept',
    strength FLOAT DEFAULT 0.5,
    occurrences INTEGER DEFAULT 1,
    source_context TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Composite indexes for graph traversal
CREATE INDEX IF NOT EXISTS idx_kg_org_source
    ON knowledge_graph_triples(organization_id, source_entity);
CREATE INDEX IF NOT EXISTS idx_kg_org_dest
    ON knowledge_graph_triples(organization_id, destination_entity);
CREATE INDEX IF NOT EXISTS idx_kg_org_rel
    ON knowledge_graph_triples(organization_id, relationship);

-- Unique constraint to prevent duplicate triples within an org
CREATE UNIQUE INDEX IF NOT EXISTS idx_kg_unique_triple
    ON knowledge_graph_triples(organization_id, source_entity, relationship, destination_entity);

-- RLS
ALTER TABLE knowledge_graph_triples ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their org graph triples"
    ON knowledge_graph_triples FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

CREATE POLICY "Users can insert graph triples for their org"
    ON knowledge_graph_triples FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

CREATE POLICY "Users can update graph triples for their org"
    ON knowledge_graph_triples FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );
