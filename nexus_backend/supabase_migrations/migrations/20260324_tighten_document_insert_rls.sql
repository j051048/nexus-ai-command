-- P0 Security Fix: Tighten Document INSERT RLS policy
--
-- The original policy had "auth.uid() IS NOT NULL" as a catch-all,
-- allowing any authenticated user to insert documents with arbitrary owner_id.
-- This tightens it to require:
--   1. owner_id must match the inserting user, OR
--   2. The user must be an admin/founder (for service-level uploads), OR
--   3. organization_id must match the user's organization (multi-tenant guard)

-- Drop the overly permissive policy
DROP POLICY IF EXISTS "Document insert policy" ON public.documents;

-- Recreated with proper constraints
CREATE POLICY "Document insert policy" ON public.documents FOR INSERT
WITH CHECK (
    -- Normal users: can only insert documents they own
    auth.uid() = owner_id
    OR
    -- Admins/founders: can insert on behalf of others within their org
    (
        EXISTS (
            SELECT 1 FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'boss')
        )
        AND (
            -- Must share organization with the document (if org_id set on both)
            organization_id IS NULL
            OR organization_id IN (
                SELECT organization_id FROM public.users WHERE id = auth.uid()
            )
        )
    )
);
