-- ============================================================================
-- Fix: approval_requests missing columns + LLM gateway tenant mismatch
-- ============================================================================

-- Bug #1: Ensure form_data and form_schema_id columns exist
-- (These were defined in 20260215_001_workflow_designer.sql but may not
--  have been applied to the live DB)
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS form_data JSONB;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS form_schema_id UUID;

-- Also ensure other workflow-related columns exist
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS on_behalf_of UUID;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS submitted_via TEXT;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS approved_by UUID;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS approval_comment TEXT;

-- Bug #2: LLM models were inserted with tenant_id='default' but the gateway
-- queries with the actual org UUID. Make organization_id nullable if it's NOT NULL,
-- or ensure 'default' tenant rows work as global fallback.
-- No schema change needed here — the fix is in the Python code (gateway fallback).
