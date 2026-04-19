-- P0-4: Enable RLS on document_embeddings (policy existed but RLS was never enabled)
ALTER TABLE document_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_embeddings FORCE ROW LEVEL SECURITY;

-- Org-isolation policy: users can only see embeddings belonging to their organization
DROP POLICY IF EXISTS document_embeddings_org_isolation ON document_embeddings;
CREATE POLICY document_embeddings_org_isolation ON document_embeddings
    FOR ALL
    USING (
        organization_id = (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );
