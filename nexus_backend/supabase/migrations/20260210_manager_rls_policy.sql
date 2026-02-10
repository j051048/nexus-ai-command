-- F5: RLS policies for manager role - department-level data isolation
-- Managers can only see users/data in their own department
-- Boss/founder can see everything

-- Policy for users table: managers see own department only
CREATE POLICY IF NOT EXISTS "managers_view_own_department" ON users
    FOR SELECT
    USING (
        -- Boss/founder see all
        (SELECT role FROM users WHERE id = auth.uid()) IN ('boss', 'founder')
        OR
        -- Managers see own department
        (
            (SELECT role FROM users WHERE id = auth.uid()) = 'manager'
            AND department = (SELECT department FROM users WHERE id = auth.uid())
        )
        OR
        -- Everyone sees themselves
        id = auth.uid()
    );

-- Policy for approval_requests: managers see own department submissions
CREATE POLICY IF NOT EXISTS "managers_view_dept_approvals" ON approval_requests
    FOR SELECT
    USING (
        (SELECT role FROM users WHERE id = auth.uid()) IN ('boss', 'founder')
        OR submitted_by = auth.uid()
        OR (
            (SELECT role FROM users WHERE id = auth.uid()) = 'manager'
            AND submitted_by IN (
                SELECT id FROM users 
                WHERE department = (SELECT department FROM users WHERE id = auth.uid())
            )
        )
    );
