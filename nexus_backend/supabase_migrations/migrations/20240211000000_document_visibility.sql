-- P0 Security Fix #4: Document Visibility Model
-- Implements three-tier visibility: private, department, organization
-- Replaces the broken "all-or-nothing" isolation model
-- ================================================================
-- 1. Add visibility column to documents table
-- ================================================================
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'organization' CHECK (
        visibility IN ('private', 'department', 'organization')
    );
-- Add department column for department-level isolation
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS department text;
-- Add index for visibility-based queries
CREATE INDEX IF NOT EXISTS idx_documents_visibility ON public.documents(visibility);
CREATE INDEX IF NOT EXISTS idx_documents_department ON public.documents(department);
-- ================================================================
-- 2. Recreate match_documents function with visibility logic
-- ================================================================
CREATE OR REPLACE FUNCTION match_documents (
        query_embedding vector(1536),
        match_threshold float,
        match_count int,
        p_user_id uuid,
        filter jsonb DEFAULT '{}'
    ) RETURNS TABLE (
        id bigint,
        content text,
        metadata jsonb,
        similarity float
    ) LANGUAGE plpgsql SECURITY DEFINER -- Run with owner privileges for cross-table access
    AS $$
DECLARE v_department text;
BEGIN -- Get the current user's department for department-level access control
SELECT department INTO v_department
FROM public.users
WHERE users.id = p_user_id;
RETURN QUERY
SELECT de.id,
    de.content,
    de.metadata,
    1 - (de.embedding <=> query_embedding) AS similarity
FROM document_embeddings de
    JOIN documents d ON de.document_id = d.id
WHERE -- Similarity threshold
    1 - (de.embedding <=> query_embedding) > match_threshold -- Metadata filter (if provided)
    AND (
        filter = '{}'
        OR de.metadata @> filter
    ) -- P0 Security: Three-tier visibility model
    AND (
        -- Rule 1: Organization-wide documents are visible to everyone
        d.visibility = 'organization' -- Rule 2: Department documents visible to same department
        OR (
            d.visibility = 'department'
            AND d.department = v_department
        ) -- Rule 3: Private documents visible only to owner
        OR (
            d.visibility = 'private'
            AND d.owner_id = p_user_id
        ) -- Rule 4: Owner always has access to their own documents
        OR d.owner_id = p_user_id
    )
ORDER BY de.embedding <=> query_embedding
LIMIT match_count;
END;
$$;
-- ================================================================
-- 3. Add RLS policies for document visibility
-- ================================================================
-- Drop existing policy if exists
DROP POLICY IF EXISTS "documents_visibility_policy" ON public.documents;
-- Create new visibility-based policy
CREATE POLICY "documents_visibility_policy" ON public.documents FOR
SELECT USING (
        -- Organization documents: everyone can see
        visibility = 'organization' -- Department documents: same department can see
        OR (
            visibility = 'department'
            AND department = (
                SELECT department
                FROM public.users
                WHERE id = auth.uid()
            )
        ) -- Private documents: only owner can see
        OR (
            visibility = 'private'
            AND owner_id = auth.uid()
        ) -- Owner always has access
        OR owner_id = auth.uid()
    );
-- ================================================================
-- 4. Comments for documentation
-- ================================================================
COMMENT ON COLUMN public.documents.visibility IS 'Document visibility level: private (owner only), department (same dept), organization (everyone)';
COMMENT ON FUNCTION match_documents IS 'P0 Security: Vector search with three-tier visibility model. Respects private/department/organization access levels.';