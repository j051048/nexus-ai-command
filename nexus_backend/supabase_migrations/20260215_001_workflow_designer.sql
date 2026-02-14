-- ============================================
-- Workflow Designer: Phase 1A Database Migration
-- Version: 20260215_001
-- Description: approval_chains table, approval_requests enhancements, RLS policies
-- ============================================

-- ============================================
-- 1. Create approval_chains table
-- ============================================
CREATE TABLE IF NOT EXISTS public.approval_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    applies_to TEXT[] NOT NULL,
    steps JSONB NOT NULL,
    conditions JSONB,
    canvas_layout JSONB,
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

-- Index for efficient lookups by org + active status
CREATE INDEX IF NOT EXISTS idx_approval_chains_org_active
    ON public.approval_chains(organization_id, is_active);

-- Index for looking up chains by applies_to type (GIN for array containment)
CREATE INDEX IF NOT EXISTS idx_approval_chains_applies_to
    ON public.approval_chains USING GIN(applies_to);

-- ============================================
-- 2. Enable RLS on approval_chains
-- ============================================
ALTER TABLE public.approval_chains ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DO $$ BEGIN
    DROP POLICY IF EXISTS "approval_chains_select_org" ON public.approval_chains;
    DROP POLICY IF EXISTS "approval_chains_insert_org" ON public.approval_chains;
    DROP POLICY IF EXISTS "approval_chains_update_org" ON public.approval_chains;
    DROP POLICY IF EXISTS "approval_chains_delete_org" ON public.approval_chains;
END $$;

-- SELECT: Users can only see chains in their organization
CREATE POLICY "approval_chains_select_org" ON public.approval_chains
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );

-- INSERT: Users can only create chains in their organization
CREATE POLICY "approval_chains_insert_org" ON public.approval_chains
    FOR INSERT WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );

-- UPDATE: Users can only update chains in their organization
CREATE POLICY "approval_chains_update_org" ON public.approval_chains
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );

-- DELETE: Users can only delete chains in their organization
CREATE POLICY "approval_chains_delete_org" ON public.approval_chains
    FOR DELETE USING (
        organization_id IN (
            SELECT organization_id FROM public.users WHERE id = auth.uid()
        )
    );

-- ============================================
-- 3. Extend approval_requests with workflow columns
-- ============================================
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS chain_id UUID REFERENCES public.approval_chains(id);
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS current_step INTEGER DEFAULT 0;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS approval_level TEXT;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS approval_history JSONB DEFAULT '[]'::jsonb;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS timeout_at TIMESTAMPTZ;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS escalated BOOLEAN DEFAULT false;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS form_data JSONB;
ALTER TABLE public.approval_requests ADD COLUMN IF NOT EXISTS form_schema_id UUID;

-- Index for timeout escalation scanning
CREATE INDEX IF NOT EXISTS idx_approval_requests_timeout
    ON public.approval_requests(timeout_at, status)
    WHERE timeout_at IS NOT NULL AND status = 'pending';

-- ============================================
-- 4. Update approval_type ENUM to include new types
-- ============================================

-- Add new enum values to the existing approval_type enum (idempotent)
DO $$
BEGIN
    -- Add 'leave' if not exists
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'leave' AND enumtypid = 'approval_type'::regtype) THEN
        ALTER TYPE approval_type ADD VALUE IF NOT EXISTS 'leave';
    END IF;
EXCEPTION WHEN undefined_object THEN
    NULL; -- Type doesn't exist, skip
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'activity' AND enumtypid = 'approval_type'::regtype) THEN
        ALTER TYPE approval_type ADD VALUE IF NOT EXISTS 'activity';
    END IF;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'custom' AND enumtypid = 'approval_type'::regtype) THEN
        ALTER TYPE approval_type ADD VALUE IF NOT EXISTS 'custom';
    END IF;
EXCEPTION WHEN undefined_object THEN
    NULL;
END $$;

-- ============================================
-- 5. Add CHECK constraint for approval_chains.applies_to values
-- ============================================
DO $$
BEGIN
    -- Drop old constraint if it exists
    ALTER TABLE public.approval_chains DROP CONSTRAINT IF EXISTS chk_approval_chains_applies_to;

    -- Add new constraint: each element in applies_to must be a valid type
    ALTER TABLE public.approval_chains ADD CONSTRAINT chk_approval_chains_applies_to
        CHECK (applies_to <@ ARRAY['travel','purchase','expense','leave','event','activity','custom']::TEXT[]);
EXCEPTION WHEN others THEN
    RAISE NOTICE 'Could not add applies_to CHECK constraint: %', SQLERRM;
END $$;

-- ============================================
-- 6. Auto-update updated_at trigger for approval_chains
-- ============================================
CREATE OR REPLACE FUNCTION update_approval_chains_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_approval_chains_updated_at'
        AND tgrelid = 'approval_chains'::regclass
    ) THEN
        CREATE TRIGGER trg_approval_chains_updated_at
        BEFORE UPDATE ON public.approval_chains
        FOR EACH ROW
        EXECUTE FUNCTION update_approval_chains_updated_at();
    END IF;
EXCEPTION WHEN undefined_table THEN
    NULL;
END $$;
