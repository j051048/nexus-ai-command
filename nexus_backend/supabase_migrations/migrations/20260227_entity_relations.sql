-- ============================================================================
-- P2-2: Lightweight Knowledge Graph - Entity Relations Table
-- Stores extracted entity relationships from conversations and tool outputs
-- enabling the AI to understand connections between customers, products, events
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.entity_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    source_entity TEXT NOT NULL,
    source_type TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    target_type TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    source_context TEXT,
    extracted_from TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    last_seen_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entity_rel_org ON public.entity_relations(org_id);
CREATE INDEX IF NOT EXISTS idx_entity_rel_source ON public.entity_relations(source_entity, source_type);
CREATE INDEX IF NOT EXISTS idx_entity_rel_target ON public.entity_relations(target_entity, target_type);
CREATE INDEX IF NOT EXISTS idx_entity_rel_relation ON public.entity_relations(relation);
CREATE INDEX IF NOT EXISTS idx_entity_rel_last_seen ON public.entity_relations(last_seen_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_rel_unique
    ON public.entity_relations(org_id, source_entity, relation, target_entity);

ALTER TABLE public.entity_relations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Org members view entity relations" ON public.entity_relations;
CREATE POLICY "Org members view entity relations"
    ON public.entity_relations
    FOR SELECT TO authenticated
    USING (
        org_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Org members insert entity relations" ON public.entity_relations;
CREATE POLICY "Org members insert entity relations"
    ON public.entity_relations
    FOR INSERT TO authenticated
    WITH CHECK (
        org_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );
