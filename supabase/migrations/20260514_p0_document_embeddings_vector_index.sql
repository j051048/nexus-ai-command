-- P0: Vector search index for document_embeddings.embedding.
-- Uses HNSW when available, falls back to IVFFLAT for older pgvector versions.

CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'document_embeddings'
          AND column_name = 'embedding'
          AND udt_name = 'vector'
    ) THEN
        BEGIN
            EXECUTE '
                CREATE INDEX IF NOT EXISTS idx_document_embeddings_embedding_hnsw
                ON public.document_embeddings
                USING hnsw (embedding vector_cosine_ops)
            ';
        EXCEPTION
            WHEN undefined_object OR feature_not_supported THEN
                EXECUTE '
                    CREATE INDEX IF NOT EXISTS idx_document_embeddings_embedding_ivfflat
                    ON public.document_embeddings
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                ';
        END;
    ELSE
        RAISE NOTICE 'document_embeddings.embedding is not vector type; skipping vector ANN index';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'document_embeddings'
          AND column_name = 'organization_id'
    ) THEN
        EXECUTE '
            CREATE INDEX IF NOT EXISTS idx_document_embeddings_org_created
            ON public.document_embeddings(organization_id, created_at DESC)
        ';
    END IF;
END $$;
