-- Fix: Add missing DELETE RLS policies for entity_aliases and knowledge_graph_triples
-- Without these, any hard DELETE on these tables silently fails for authenticated users.

CREATE POLICY IF NOT EXISTS "Users can delete entity aliases for their org"
    ON entity_aliases FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );

CREATE POLICY IF NOT EXISTS "Users can delete graph triples for their org"
    ON knowledge_graph_triples FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.users
            WHERE id = auth.uid()
        )
    );
