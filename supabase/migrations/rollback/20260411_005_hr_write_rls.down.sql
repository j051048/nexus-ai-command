-- ROLLBACK: 20260411_005_hr_write_rls.sql
-- Risk: MEDIUM — only drops RLS policies and index; does NOT drop hr_employees table
-- Safe to run: removes write permissions but preserves data

BEGIN;

-- 1. hr_candidates policies
DROP POLICY IF EXISTS "Org Update for Candidates" ON hr_candidates;
DROP POLICY IF EXISTS "Org Insert for Candidates" ON hr_candidates;

-- 2. hr_performance_reviews policies
DROP POLICY IF EXISTS "Org Update for Performance Reviews" ON hr_performance_reviews;
DROP POLICY IF EXISTS "Org Insert for Performance Reviews" ON hr_performance_reviews;

-- 3. hr_employees policies
DROP POLICY IF EXISTS "Org Update for Employees" ON hr_employees;
DROP POLICY IF EXISTS "Org Insert for Employees" ON hr_employees;
DROP POLICY IF EXISTS "Org Isolation for Employees" ON hr_employees;

-- 4. Index
DROP INDEX IF EXISTS idx_hr_employees_org;

-- NOTE: hr_employees table is NOT dropped because it may have been created
-- by an earlier migration or may contain employee data.
-- The organization_id column is also preserved.

COMMIT;
