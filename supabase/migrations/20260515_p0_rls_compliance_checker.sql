-- P0 Audit Fix: RLS Compliance Checker
-- This function can be called in CI/CD to detect tables missing RLS.
-- Usage: SELECT * FROM public.check_rls_compliance();

CREATE OR REPLACE FUNCTION public.check_rls_compliance()
RETURNS TABLE (
    table_schema TEXT,
    table_name TEXT,
    rls_enabled BOOLEAN,
    has_policies BOOLEAN,
    compliance_status TEXT
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT
        t.schemaname::TEXT AS table_schema,
        t.tablename::TEXT AS table_name,
        t.rowsecurity AS rls_enabled,
        EXISTS (
            SELECT 1
            FROM pg_policies p
            WHERE p.schemaname = t.schemaname
              AND p.tablename = t.tablename
        ) AS has_policies,
        CASE
            WHEN t.rowsecurity AND EXISTS (
                SELECT 1 FROM pg_policies p
                WHERE p.schemaname = t.schemaname AND p.tablename = t.tablename
            ) THEN 'COMPLIANT'
            WHEN t.rowsecurity AND NOT EXISTS (
                SELECT 1 FROM pg_policies p
                WHERE p.schemaname = t.schemaname AND p.tablename = t.tablename
            ) THEN 'WARNING: RLS enabled but no policies defined'
            ELSE 'NON_COMPLIANT: RLS not enabled'
        END AS compliance_status
    FROM pg_tables t
    WHERE t.schemaname = 'public'
      AND t.tablename NOT LIKE 'pg_%'
      AND t.tablename NOT LIKE '_prisma_%'
      AND t.tablename != 'schema_migrations'
      AND t.tablename != 'supabase_migrations'
    ORDER BY
        CASE
            WHEN NOT t.rowsecurity THEN 0  -- Non-compliant first
            ELSE 1
        END,
        t.tablename;
$$;

-- Grant access to authenticated users (admin endpoints can call this)
GRANT EXECUTE ON FUNCTION public.check_rls_compliance() TO authenticated;

COMMENT ON FUNCTION public.check_rls_compliance() IS
    'P0 Audit: Returns RLS compliance status for all public tables. '
    'Non-compliant tables appear first. Use in CI to block deployments '
    'that introduce unprotected tables.';
