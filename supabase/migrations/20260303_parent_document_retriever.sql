-- P2: Parent-Document Retriever support
-- Adds parent_chunk_id and chunk_type to document_embeddings
-- Enables retrieving broader context when a small chunk matches

ALTER TABLE document_embeddings
    ADD COLUMN IF NOT EXISTS parent_chunk_id UUID REFERENCES document_embeddings(id),
    ADD COLUMN IF NOT EXISTS chunk_type TEXT NOT NULL DEFAULT 'child';

COMMENT ON COLUMN document_embeddings.parent_chunk_id IS 'Reference to parent chunk for parent-document retrieval';
COMMENT ON COLUMN document_embeddings.chunk_type IS 'parent or child — parent chunks are larger context windows';

CREATE INDEX IF NOT EXISTS idx_doc_embeddings_parent
    ON document_embeddings(parent_chunk_id) WHERE parent_chunk_id IS NOT NULL;
