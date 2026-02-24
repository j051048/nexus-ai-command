-- Add expires_at column for Knowledge Base auto-expiry/GC
-- Allows documents to have a configurable expiration date
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'document_embeddings' AND column_name = 'expires_at') THEN
    ALTER TABLE document_embeddings ADD COLUMN expires_at timestamptz;
  END IF;
END $$;

-- Index for efficient GC queries
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_expires
  ON document_embeddings(organization_id, expires_at)
  WHERE expires_at IS NOT NULL;

-- Index for staleness check (organization + created/updated time)
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_org_updated
  ON document_embeddings(organization_id, created_at);
