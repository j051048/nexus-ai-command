-- Migration: 20260311_restore_fts_keyword_search.sql
-- Purpose: Restore FTS-based keyword search (was regressed to ILIKE in 20260214)
--
-- The fts tsvector column + GIN index already exist from 20240201000000_add_fts_index.sql.
-- This migration only replaces the match_documents_keyword RPC function.
-- Performance: FTS with GIN index is ~100x faster than ILIKE '%query%' full table scan.

-- Ensure FTS column and indexes exist (idempotent safety)
ALTER TABLE document_embeddings
ADD COLUMN IF NOT EXISTS fts tsvector
GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;

CREATE INDEX IF NOT EXISTS document_embeddings_fts_idx
ON document_embeddings USING gin(fts);

-- Drop existing function first (PostgreSQL cannot change parameter defaults in-place)
DROP FUNCTION IF EXISTS match_documents_keyword(text, uuid, int, uuid);

-- Recreate with FTS-based search instead of ILIKE
CREATE OR REPLACE FUNCTION match_documents_keyword(
    p_query text,
    p_user_id uuid,
    p_limit int,
    p_org_id uuid DEFAULT NULL
) RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity float,
    organization_id uuid
) LANGUAGE plpgsql AS $$
DECLARE
    v_tsquery tsquery;
BEGIN
    -- Build tsquery using 'simple' config (works for CJK per-character tokenization)
    v_tsquery := plainto_tsquery('simple', p_query);

    RETURN QUERY
    SELECT
        de.id,
        de.content,
        de.metadata,
        ts_rank(de.fts, v_tsquery)::float AS similarity,
        d.organization_id
    FROM document_embeddings de
    JOIN documents d ON d.id = de.document_id
    WHERE
        de.fts @@ v_tsquery
        AND (
            p_org_id IS NULL
            OR d.organization_id = p_org_id
        )
        AND (
            d.visibility = 'organization'
            OR (
                d.visibility = 'private'
                AND d.owner_id = p_user_id
            )
            OR (
                d.visibility = 'department'
                AND d.department_id = (
                    SELECT department_id
                    FROM users
                    WHERE users.id = p_user_id
                )
            )
        )
    ORDER BY similarity DESC
    LIMIT p_limit;
END;
$$;
