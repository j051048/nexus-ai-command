-- ROLLBACK: 20260410_report_engine.sql
-- Risk: HIGH — saved_reports and report_schedules may contain user data

BEGIN;

-- 1. Triggers (must drop before tables)
DROP TRIGGER IF EXISTS trg_report_schedules_updated ON report_schedules;
DROP TRIGGER IF EXISTS trg_saved_reports_updated ON saved_reports;

-- 2. Functions
DROP FUNCTION IF EXISTS update_report_schedules_updated_at();
DROP FUNCTION IF EXISTS update_saved_reports_updated_at();

-- 3. Policies
DROP POLICY IF EXISTS "report_schedules_org_isolation" ON report_schedules;
DROP POLICY IF EXISTS "saved_reports_select_public" ON saved_reports;
DROP POLICY IF EXISTS "saved_reports_org_isolation" ON saved_reports;

-- 4. Tables (report_schedules references saved_reports, drop child first)
-- WARNING: This will permanently delete all saved reports and schedules
DROP TABLE IF EXISTS report_schedules;
DROP TABLE IF EXISTS saved_reports;

COMMIT;
