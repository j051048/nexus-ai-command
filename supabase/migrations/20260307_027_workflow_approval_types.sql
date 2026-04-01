-- ============================================
-- Update approval_chains CHECK constraint
-- Version: 20260307_027
-- Description: Add 'general' and 'contract' to valid approval types
-- ============================================

DO $$
BEGIN
    -- Drop old constraint
    ALTER TABLE public.approval_chains DROP CONSTRAINT IF EXISTS chk_approval_chains_applies_to;

    -- Add updated constraint with 'general' and 'contract'
    ALTER TABLE public.approval_chains ADD CONSTRAINT chk_approval_chains_applies_to
        CHECK (applies_to <@ ARRAY['travel','purchase','expense','leave','event','activity','custom','general','contract']::TEXT[]);
EXCEPTION WHEN others THEN
    RAISE NOTICE 'Could not update applies_to CHECK constraint: %', SQLERRM;
END $$;
