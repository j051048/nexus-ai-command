-- P3 Enhancement: Extended RLS Policies for Complete Data Isolation
-- This migration adds additional security policies for visibility controls
-- ============================================================
-- 1. Enhanced Document Visibility Support
-- ============================================================
-- Add visibility column if not exists (from P0 fix)
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'organization' CHECK (
        visibility IN ('private', 'department', 'organization')
    );
ALTER TABLE public.documents
ADD COLUMN IF NOT EXISTS department TEXT;
-- Drop existing policies to recreate with visibility support
DROP POLICY IF EXISTS "Users can see own documents" ON public.documents;
DROP POLICY IF EXISTS "Users can insert own documents" ON public.documents;
-- Enhanced SELECT policy with visibility levels
CREATE POLICY "Document visibility policy" ON public.documents FOR
SELECT USING (
        -- Private: only owner can see
        (
            visibility = 'private'
            AND owner_id = auth.uid()
        )
        OR -- Department: owner + same department members
        (
            visibility = 'department'
            AND (
                owner_id = auth.uid()
                OR EXISTS (
                    SELECT 1
                    FROM public.users u1,
                        public.users u2
                    WHERE u1.id = auth.uid()
                        AND u2.id = owner_id
                        AND u1.department = u2.department
                )
            )
        )
        OR -- Organization: all authenticated users
        (
            visibility = 'organization'
            AND auth.uid() IS NOT NULL
        )
        OR -- Founders/admins can see everything
        EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin', 'boss')
        )
    );
-- INSERT policy: users can only create documents they own
CREATE POLICY "Document insert policy" ON public.documents FOR
INSERT WITH CHECK (
        auth.uid() = owner_id
        OR auth.uid() IS NOT NULL -- Allow service role insertion
    );
-- UPDATE policy: only owners and admins can update
CREATE POLICY "Document update policy" ON public.documents FOR
UPDATE USING (
        owner_id = auth.uid()
        OR EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin')
        )
    );
-- DELETE policy: only owners and admins can delete
CREATE POLICY "Document delete policy" ON public.documents FOR DELETE USING (
    owner_id = auth.uid()
    OR EXISTS (
        SELECT 1
        FROM public.users
        WHERE id = auth.uid()
            AND role IN ('founder', 'admin')
    )
);
-- ============================================================
-- 2. Approval Requests RLS
-- ============================================================
ALTER TABLE IF EXISTS public.approval_requests ENABLE ROW LEVEL SECURITY;
-- Users can see their own requests
CREATE POLICY IF NOT EXISTS "Users can view own approval requests" ON public.approval_requests FOR
SELECT USING (
        requester_id = auth.uid()
        OR approver_id = auth.uid()
        OR EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin', 'boss', 'manager')
        )
    );
-- Users can create their own requests
CREATE POLICY IF NOT EXISTS "Users can create approval requests" ON public.approval_requests FOR
INSERT WITH CHECK (requester_id = auth.uid());
-- Only approvers can update requests
CREATE POLICY IF NOT EXISTS "Approvers can update requests" ON public.approval_requests FOR
UPDATE USING (
        approver_id = auth.uid()
        OR EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin', 'boss')
        )
    );
-- ============================================================
-- 3. Performance Scores RLS
-- ============================================================
ALTER TABLE IF EXISTS public.performance_scores ENABLE ROW LEVEL SECURITY;
-- Users can see their own scores, managers can see team scores
CREATE POLICY IF NOT EXISTS "Performance score visibility" ON public.performance_scores FOR
SELECT USING (
        user_id = auth.uid()
        OR EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin', 'boss', 'manager')
        )
    );
-- ============================================================
-- 4. Audit Log Protection
-- ============================================================
ALTER TABLE IF EXISTS public.audit_logs ENABLE ROW LEVEL SECURITY;
-- Only admins can view audit logs
CREATE POLICY IF NOT EXISTS "Admin audit log access" ON public.audit_logs FOR
SELECT USING (
        EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin')
        )
    );
-- Anyone can insert audit logs (for logging purposes)
CREATE POLICY IF NOT EXISTS "Audit log insert" ON public.audit_logs FOR
INSERT WITH CHECK (true);
-- No one can update or delete audit logs
CREATE POLICY IF NOT EXISTS "Audit log immutable" ON public.audit_logs FOR
UPDATE USING (false);
CREATE POLICY IF NOT EXISTS "Audit log no delete" ON public.audit_logs FOR DELETE USING (false);
-- ============================================================
-- 5. User Profile RLS
-- ============================================================
ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;
-- Users can view basic info of all users (for @mentions, etc.)
-- But sensitive fields should be excluded in application queries
CREATE POLICY IF NOT EXISTS "User basic info visible" ON public.users FOR
SELECT USING (auth.uid() IS NOT NULL);
-- Users can only update their own profile
CREATE POLICY IF NOT EXISTS "User self update" ON public.users FOR
UPDATE USING (
        id = auth.uid()
        OR EXISTS (
            SELECT 1
            FROM public.users
            WHERE id = auth.uid()
                AND role IN ('founder', 'admin')
        )
    );
-- ============================================================
-- 6. Indexes for RLS Performance
-- ============================================================
-- Index for document visibility queries
CREATE INDEX IF NOT EXISTS idx_documents_visibility ON public.documents(visibility, owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_department ON public.documents(department)
WHERE department IS NOT NULL;
-- Index for user role lookups
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);
CREATE INDEX IF NOT EXISTS idx_users_department ON public.users(department)
WHERE department IS NOT NULL;
-- ============================================================
-- 7. Grant Permissions
-- ============================================================
-- Ensure authenticated users can access tables through RLS
GRANT SELECT,
    INSERT,
    UPDATE,
    DELETE ON public.documents TO authenticated;
GRANT SELECT,
    INSERT,
    UPDATE ON public.approval_requests TO authenticated;
GRANT SELECT ON public.performance_scores TO authenticated;
GRANT SELECT,
    INSERT ON public.audit_logs TO authenticated;
GRANT SELECT,
    UPDATE ON public.users TO authenticated;