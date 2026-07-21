-- Canonical enterprise knowledge retrieval contract.
-- Fixes filename-blind RAG, legacy RPC result shapes and permissive ACL policy.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_documents_org_name_trgm
    ON public.documents USING gin (lower(name) gin_trgm_ops);

DROP POLICY IF EXISTS document_embeddings_acl_policy ON public.document_embeddings;
DROP FUNCTION IF EXISTS public.check_document_access(uuid, uuid);
DROP FUNCTION IF EXISTS public.check_document_access(uuid, bigint);

CREATE OR REPLACE FUNCTION public.check_document_access(
    p_user_id uuid,
    p_document_id bigint
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    document_groups text[];
    allowed boolean := false;
BEGIN
    SELECT de.access_groups
      INTO document_groups
      FROM public.document_embeddings de
     WHERE de.id = p_document_id;
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    IF document_groups IS NULL OR cardinality(document_groups) = 0 THEN
        RETURN true;
    END IF;
    IF p_user_id IS NULL
       OR to_regclass('public.user_group_memberships') IS NULL THEN
        RETURN false;
    END IF;
    EXECUTE
        'SELECT EXISTS ('
        'SELECT 1 FROM public.user_group_memberships '
        'WHERE user_id = $1 AND group_name = ANY($2)'
        ')'
        INTO allowed
        USING p_user_id, document_groups;
    RETURN allowed;
END;
$$;

-- Multiple permissive policies are OR-ed by PostgreSQL.  The previous ACL
-- policy therefore could bypass the org policy for rows with empty groups.
DROP POLICY IF EXISTS document_embeddings_acl_policy
    ON public.document_embeddings;
CREATE POLICY document_embeddings_acl_policy
    ON public.document_embeddings
    AS RESTRICTIVE
    FOR SELECT
    USING (
        access_groups IS NULL
        OR cardinality(access_groups) = 0
        OR check_document_access(
            NULLIF(current_setting('app.current_user_id', true), '')::uuid,
            id
        )
    );

-- Remove all historical overloads before publishing one stable RPC contract.
DO $$
DECLARE
    function_signature text;
BEGIN
    FOR function_signature IN
        SELECT p.oid::regprocedure::text
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN ('match_documents', 'match_documents_keyword')
    LOOP
        EXECUTE 'DROP FUNCTION IF EXISTS ' || function_signature;
    END LOOP;
END;
$$;

CREATE FUNCTION public.match_documents(
    query_embedding vector(1536),
    match_threshold double precision DEFAULT 0.4,
    match_count integer DEFAULT 6,
    filter jsonb DEFAULT '{}'::jsonb,
    p_user_id uuid DEFAULT NULL,
    p_org_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    content text,
    metadata jsonb,
    doc_metadata jsonb,
    doc_type text,
    parent_chunk_id uuid,
    chunk_type text,
    organization_id uuid,
    similarity double precision
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    user_department text;
BEGIN
    IF p_user_id IS NULL OR p_org_id IS NULL THEN
        RETURN;
    END IF;
    IF auth.uid() IS NOT NULL AND auth.uid() <> p_user_id THEN
        RETURN;
    END IF;

    SELECT u.department
      INTO user_department
      FROM public.users u
     WHERE u.id = p_user_id
       AND u.organization_id = p_org_id;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        de.id,
        de.document_id,
        de.content,
        de.metadata,
        jsonb_build_object(
            'document_id', d.id,
            'title', d.name,
            'source', d.name,
            'doc_type', d.doc_type,
            'source_version', d.source_version,
            'valid_until', d.valid_until,
            'review_status', d.review_status
        ),
        COALESCE(d.doc_type::text, 'other'),
        de.parent_chunk_id,
        de.chunk_type::text,
        de.organization_id,
        1 - (de.embedding <=> query_embedding)
    FROM public.document_embeddings de
    JOIN public.documents d ON d.id = de.document_id
    WHERE de.organization_id = p_org_id
      AND d.organization_id = p_org_id
      AND d.status IN ('ready', 'completed')
      AND COALESCE(d.review_status, 'pending') NOT IN ('rejected', 'expired')
      AND (d.valid_until IS NULL OR d.valid_until >= CURRENT_DATE)
      AND (
          COALESCE(d.visibility, 'organization') IN ('organization', 'public')
          OR d.owner_id = p_user_id
          OR (
              d.visibility = 'department'
              AND d.department = user_department
          )
      )
      AND public.check_document_access(p_user_id, de.id)
      AND (filter = '{}'::jsonb OR de.metadata @> filter)
      AND 1 - (de.embedding <=> query_embedding) >= match_threshold
    ORDER BY de.embedding <=> query_embedding
    LIMIT LEAST(GREATEST(match_count, 1), 20);
END;
$$;

CREATE FUNCTION public.match_documents_keyword(
    p_query text,
    p_user_id uuid,
    p_limit integer DEFAULT 6,
    p_org_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    content text,
    metadata jsonb,
    doc_metadata jsonb,
    doc_type text,
    parent_chunk_id uuid,
    chunk_type text,
    organization_id uuid,
    similarity double precision
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
    user_department text;
    normalized_query text := lower(trim(COALESCE(p_query, '')));
BEGIN
    IF normalized_query = '' OR p_user_id IS NULL OR p_org_id IS NULL THEN
        RETURN;
    END IF;
    IF auth.uid() IS NOT NULL AND auth.uid() <> p_user_id THEN
        RETURN;
    END IF;

    SELECT u.department
      INTO user_department
      FROM public.users u
     WHERE u.id = p_user_id
       AND u.organization_id = p_org_id;
    IF NOT FOUND THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT
        de.id,
        de.document_id,
        de.content,
        de.metadata,
        jsonb_build_object(
            'document_id', d.id,
            'title', d.name,
            'source', d.name,
            'doc_type', d.doc_type,
            'source_version', d.source_version,
            'valid_until', d.valid_until,
            'review_status', d.review_status
        ),
        COALESCE(d.doc_type::text, 'other'),
        de.parent_chunk_id,
        de.chunk_type::text,
        de.organization_id,
        GREATEST(
            similarity(lower(d.name), normalized_query),
            word_similarity(lower(d.name), normalized_query),
            CASE
                WHEN normalized_query LIKE '%' || lower(d.name) || '%' THEN 1.0
                WHEN lower(d.name) LIKE '%' || normalized_query || '%' THEN 0.98
                WHEN lower(de.content) LIKE '%' || normalized_query || '%' THEN 0.9
                ELSE 0.0
            END,
            COALESCE(ts_rank(de.fts, websearch_to_tsquery('simple', p_query)), 0)
        )::double precision
    FROM public.document_embeddings de
    JOIN public.documents d ON d.id = de.document_id
    WHERE de.organization_id = p_org_id
      AND d.organization_id = p_org_id
      AND d.status IN ('ready', 'completed')
      AND COALESCE(d.review_status, 'pending') NOT IN ('rejected', 'expired')
      AND (d.valid_until IS NULL OR d.valid_until >= CURRENT_DATE)
      AND (
          COALESCE(d.visibility, 'organization') IN ('organization', 'public')
          OR d.owner_id = p_user_id
          OR (
              d.visibility = 'department'
              AND d.department = user_department
          )
      )
      AND public.check_document_access(p_user_id, de.id)
      AND (
          normalized_query LIKE '%' || lower(d.name) || '%'
          OR lower(d.name) LIKE '%' || normalized_query || '%'
          OR similarity(lower(d.name), normalized_query) >= 0.18
          OR word_similarity(lower(d.name), normalized_query) >= 0.35
          OR lower(de.content) LIKE '%' || normalized_query || '%'
          OR de.fts @@ websearch_to_tsquery('simple', p_query)
      )
    ORDER BY 10 DESC, d.updated_at DESC
    LIMIT LEAST(GREATEST(p_limit, 1), 20);
END;
$$;

REVOKE ALL ON FUNCTION public.match_documents(
    vector, double precision, integer, jsonb, uuid, uuid
) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.match_documents_keyword(
    text, uuid, integer, uuid
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.match_documents(
    vector, double precision, integer, jsonb, uuid, uuid
) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.match_documents_keyword(
    text, uuid, integer, uuid
) TO authenticated, service_role;

COMMENT ON FUNCTION public.match_documents(
    vector, double precision, integer, jsonb, uuid, uuid
) IS 'Tenant-scoped vector retrieval with canonical document identity and ACL enforcement.';
COMMENT ON FUNCTION public.match_documents_keyword(
    text, uuid, integer, uuid
) IS 'Tenant-scoped filename/content retrieval with canonical document identity and ACL enforcement.';
