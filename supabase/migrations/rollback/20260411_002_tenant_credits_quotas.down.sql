-- ROLLBACK: 20260411_002_tenant_credits_quotas.sql
-- Risk: CRITICAL — billing credits and quotas; consume_tenant_credit RPC is core billing function
-- DO NOT run in production without data backup and stakeholder approval!

BEGIN;

-- 1. Function (dropping this immediately disables credit consumption)
DROP FUNCTION IF EXISTS consume_tenant_credit(TEXT, TEXT, BIGINT, TEXT);

-- 2. Policies
DROP POLICY IF EXISTS "tenant_quotas_org_isolation" ON tenant_quotas;
DROP POLICY IF EXISTS "tenant_credits_org_isolation" ON tenant_credits;

-- 3. Indexes
DROP INDEX IF EXISTS idx_tenant_credits_org;
DROP INDEX IF EXISTS idx_tenant_credits_type;

-- 4. Tables
-- WARNING: Contains tenant credit balances and quota configurations!
DROP TABLE IF EXISTS tenant_quotas;
DROP TABLE IF EXISTS tenant_credits;

COMMIT;
