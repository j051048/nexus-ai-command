-- Secure match_documents with user_id filtering to prevent cross-tenant data leakage.
-- This ensures that RAG retrieval only returns documents owned by the specific user (or all if user is founder, though here we enforce direct ownership for simplicity).
DROP FUNCTION IF EXISTS match_documents;
CREATE OR REPLACE FUNCTION match_documents (
        query_embedding vector(1536),
        match_threshold float,
        match_count int,
        p_user_id uuid,
        -- Required parameter for security
        filter jsonb DEFAULT '{}'
    ) RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        similarity float
    ) LANGUAGE plpgsql AS $$ BEGIN RETURN QUERY
SELECT de.id,
    de.content,
    de.metadata,
    1 - (de.embedding <=> query_embedding) AS similarity
FROM document_embeddings de
    JOIN documents d ON de.document_id = d.id
WHERE 1 - (de.embedding <=> query_embedding) > match_threshold
    AND d.owner_id = p_user_id -- Strict tenant isolation
    AND de.metadata @> filter
ORDER BY de.embedding <=> query_embedding
LIMIT match_count;
END;
$$;