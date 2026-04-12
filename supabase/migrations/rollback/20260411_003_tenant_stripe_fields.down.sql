-- ROLLBACK: 20260411_003_tenant_stripe_fields.sql
-- Risk: CRITICAL — stripe_customer_id links orgs to Stripe, tier controls feature access
-- DO NOT run in production without data backup and stakeholder approval!

BEGIN;

DROP INDEX IF EXISTS idx_orgs_tier;
DROP INDEX IF EXISTS idx_orgs_stripe_customer;
ALTER TABLE organizations DROP COLUMN IF EXISTS payment_status;
ALTER TABLE organizations DROP COLUMN IF EXISTS tier;
ALTER TABLE organizations DROP COLUMN IF EXISTS stripe_customer_id;

COMMIT;
