-- ============================================
-- Approval Chain Upgrade Migration
-- Version: 20260227
-- Description: P2 manager_id support for org hierarchy,
--              P4 new node types validation support
-- ============================================

-- ============================================
-- P2: Add manager_id for org hierarchy
-- ============================================
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES auth.users(id);

-- Index for efficient manager lookups
CREATE INDEX IF NOT EXISTS idx_users_manager_id ON public.users(manager_id);

-- ============================================
-- P4: Add new node types to workflow validation
-- (No schema change needed - steps JSONB already supports any type)
-- New supported node types: cc_notify, timer, sub_workflow
-- These are additive and backward-compatible with existing workflows.
-- ============================================

-- Add a comment documenting the supported node types
COMMENT ON COLUMN public.approval_chains.steps IS
'JSONB array of workflow step nodes. Supported types: approver, condition, parallel, auto_approve, notify, cc_notify, timer, sub_workflow';
