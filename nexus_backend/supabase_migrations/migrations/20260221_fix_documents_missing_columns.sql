-- ============================================================
-- Fix documents & document_embeddings missing columns
-- Root cause: upload fails with "Could not find the 'content_hash'
-- column of 'documents' in the schema cache"
-- ============================================================

-- 1. documents: add missing columns
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS content_hash text,
    ADD COLUMN IF NOT EXISTS error_log text,
    ADD COLUMN IF NOT EXISTS category text DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedding_model_version text,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz;

-- Index on content_hash for dedup lookups
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON public.documents(content_hash);
-- Index on owner_id for user queries
CREATE INDEX IF NOT EXISTS idx_documents_owner ON public.documents(owner_id);
-- Index on organization_id for org queries
CREATE INDEX IF NOT EXISTS idx_documents_org ON public.documents(organization_id);

-- 2. document_embeddings: add missing columns
ALTER TABLE public.document_embeddings
    ADD COLUMN IF NOT EXISTS chunk_index integer,
    ADD COLUMN IF NOT EXISTS content_hash text,
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedding_model_version text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

-- Index on document_id for joining
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_doc_id ON public.document_embeddings(document_id);
-- Index on organization_id for org isolation
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_org ON public.document_embeddings(organization_id);

-- 3. HNSW vector index for efficient similarity search
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_vector
    ON public.document_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
