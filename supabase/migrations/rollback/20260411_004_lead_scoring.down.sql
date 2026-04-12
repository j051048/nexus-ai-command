-- ROLLBACK: 20260411_004_lead_scoring.sql
-- Risk: MEDIUM — AI-generated scores will be lost, CRM module impact only

BEGIN;

DROP INDEX IF EXISTS idx_sales_leads_win_prob;
DROP INDEX IF EXISTS idx_sales_leads_score;
ALTER TABLE sales_leads DROP COLUMN IF EXISTS last_scored_at;
ALTER TABLE sales_leads DROP COLUMN IF EXISTS ai_suggestion;
ALTER TABLE sales_leads DROP COLUMN IF EXISTS win_probability;
ALTER TABLE sales_leads DROP COLUMN IF EXISTS score;

COMMIT;
