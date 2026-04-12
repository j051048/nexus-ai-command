-- ROLLBACK: 20260411_001_subscriptions.sql
-- Risk: CRITICAL — billing core tables, contains Stripe subscription data
-- DO NOT run in production without data backup and stakeholder approval!

BEGIN;

-- 1. Policies
DROP POLICY IF EXISTS "tenant_subscriptions_org_isolation" ON tenant_subscriptions;
DROP POLICY IF EXISTS "subscriptions_org_isolation" ON subscriptions;

-- 2. Indexes
DROP INDEX IF EXISTS idx_tenant_sub_status;
DROP INDEX IF EXISTS idx_tenant_sub_tenant;
DROP INDEX IF EXISTS idx_subscriptions_status;
DROP INDEX IF EXISTS idx_subscriptions_plan;

-- 3. Tables
-- WARNING: Contains active subscription and payment data!
DROP TABLE IF EXISTS tenant_subscriptions;
DROP TABLE IF EXISTS subscriptions;

COMMIT;
