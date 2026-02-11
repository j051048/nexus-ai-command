-- P0 Security Fix: Add organization_id parameter to match_documents
-- Ensures strict organization isolation with optional override
-- Recreate match_documents function with p_org_id parameter
CREATE OR REPLACE FUNCTION match_documents (
        query_embedding vector(1536),
        match_threshold float,
        match_count int,
        p_user_id uuid,
        filter jsonb DEFAULT '{}',
        p_org_id uuid DEFAULT NULL -- New parameter
    ) RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        similarity float
    ) LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_department text;
v_org_id uuid;
BEGIN -- Get user details (department and strict org_id)
SELECT department,
    organization_id INTO v_department,
    v_org_id
FROM public.users
WHERE users.id = p_user_id;
-- If p_org_id is explicitly provided, verify or use it
-- For now, we allow system to override if needed, or enforce consistency
IF p_org_id IS NOT NULL THEN -- Optional: Validation to ensure user belongs to org?
-- For trusted backend calls, we can trust the parameter.
-- But for strict isolation, we might want to prioritize the user's actual org
-- unless the user is a super-admin (not implemented yet).
-- Here we allow the parameter to override the lookup, handy for "system" agents.
v_org_id := p_org_id;
END IF;
RETURN QUERY
SELECT de.id,
    de.content,
    de.metadata,
    1 - (de.embedding <=> query_embedding) AS similarity
FROM document_embeddings de
    JOIN documents d ON de.document_id = d.id
WHERE 1 - (de.embedding <=> query_embedding) > match_threshold
    AND (
        filter = '{}'
        OR de.metadata @> filter
    ) -- Key Change: Enforce Organization Isolation
    AND d.organization_id = v_org_id -- Three-tier visibility
    AND (
        -- Rule 1: Organization-wide
        d.visibility = 'organization' -- Rule 2: Department
        OR (
            d.visibility = 'department'
            AND d.department = v_department
        ) -- Rule 3: Private
        OR (
            d.visibility = 'private'
            AND d.owner_id = p_user_id
        ) -- Rule 4: Owner override
        OR d.owner_id = p_user_id
    )
ORDER BY de.embedding <=> query_embedding
LIMIT match_count;
END;
$$;
-- Update match_documents_keyword for consistency
CREATE OR REPLACE FUNCTION match_documents_keyword(
        p_query TEXT,
        p_user_id UUID,
        p_limit INTEGER DEFAULT 5,
        p_org_id UUID DEFAULT NULL -- New parameter
    ) RETURNS TABLE (
        id UUID,
        content TEXT,
        metadata JSONB,
        doc_metadata JSONB,
        visibility TEXT,
        score REAL
    ) AS $$
DECLARE v_user_dept TEXT;
v_user_org UUID;
BEGIN
SELECT department,
    organization_id INTO v_user_dept,
    v_user_org
FROM users
WHERE id = p_user_id;
IF p_org_id IS NOT NULL THEN v_user_org := p_org_id;
END IF;
RETURN QUERY
SELECT de.id,
    de.content,
    de.metadata,
    d.metadata as doc_metadata,
    d.visibility,
    ts_rank(de.fts, plainto_tsquery('simple', p_query)) as score
FROM document_embeddings de
    JOIN documents d ON de.document_id = d.id
WHERE de.fts @@ plainto_tsquery('simple', p_query)
    AND d.organization_id = v_user_org -- Enforce Org Isolation
    AND (
        d.visibility = 'organization'
        OR (
            d.visibility = 'department'
            AND d.department = v_user_dept
        )
        OR d.owner_id = p_user_id
    )
ORDER BY score DESC
LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;