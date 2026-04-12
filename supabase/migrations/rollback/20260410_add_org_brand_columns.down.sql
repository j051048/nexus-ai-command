-- ROLLBACK: 20260410_add_org_brand_columns.sql
-- Risk: MEDIUM — brand JSONB column may contain tenant branding config

BEGIN;

COMMENT ON COLUMN organizations.brand IS NULL;
DROP INDEX IF EXISTS idx_organizations_brand;
ALTER TABLE organizations DROP COLUMN IF EXISTS brand;

COMMIT;
