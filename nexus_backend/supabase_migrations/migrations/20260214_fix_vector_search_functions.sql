-- Migration: 20260214_fix_vector_search_functions.sql
-- Purpose: Fix match_documents RPC to handle visibility and define missing match_documents_keyword RPC.
-- 1. Fix match_documents RPC (Semantic Search)
CREATE OR REPLACE FUNCTION match_documents(
        query_embedding vector(1536),
        match_threshold float,
        match_count int,
        filter jsonb DEFAULT '{}',
        p_user_id uuid DEFAULT NULL,
        p_org_id uuid DEFAULT NULL
    ) RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        similarity float,
        organization_id uuid
    ) LANGUAGE plpgsql AS $$ BEGIN RETURN QUERY
SELECT de.id,
    de.content,
    de.metadata,
    1 - (de.embedding <=> query_embedding) as similarity,
    de.organization_id
FROM document_embeddings de
    JOIN documents d ON d.id = de.document_id
WHERE 1 - (de.embedding <=> query_embedding) > match_threshold
    AND (
        -- Organization Filter (Strict)
        (
            p_org_id IS NULL
            OR d.organization_id = p_org_id
        )
        AND (
            -- Visibility Filter (Three-Tier Model)
            d.visibility = 'organization'
            OR (
                d.visibility = 'private'
                AND d.owner_id = p_user_id
            ) -- Department logic
            OR (
                d.visibility = 'department'
                AND d.department_id = (
                    SELECT department_id
                    FROM users
                    WHERE id = p_user_id
                )
            ) -- Fallback if department_id is null? Or department name? 
            -- Let's stick to department_id as primary link.
        )
    )
ORDER BY de.embedding <=> query_embedding
LIMIT match_count;
END;
$$;
-- 2. Define match_documents_keyword RPC (Keyword Search)
CREATE OR REPLACE FUNCTION match_documents_keyword(
        p_query text,
        p_user_id uuid,
        p_limit int,
        p_org_id uuid DEFAULT NULL
    ) RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        -- Return metadata to match Python expectation
        similarity float,
        -- Dummy for compatibility
        organization_id uuid
    ) LANGUAGE plpgsql AS $$ BEGIN RETURN QUERY
SELECT de.id,
    de.content,
    de.metadata,
    0.0::float as similarity,
    d.organization_id
FROM document_embeddings de
    JOIN documents d ON d.id = de.document_id
WHERE -- Keyword Match (Simple ILIKE for robustness)
    de.content ILIKE '%' || p_query || '%'
    AND (
        -- Organization Filter
        (
            p_org_id IS NULL
            OR d.organization_id = p_org_id
        )
        AND (
            -- Visibility Filter
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
                    WHERE id = p_user_id
                )
            )
        )
    )
ORDER BY de.created_at DESC
LIMIT p_limit;
END;
$$;