-- Migration: 20260215_002_form_schemas
-- Purpose: Create form_schemas table for custom form engine
-- Supports dynamic form definitions per approval type per organization

-- ============================================
-- 1. Create form_schemas table
-- ============================================

CREATE TABLE IF NOT EXISTS public.form_schemas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    approval_type text NOT NULL,
    name text NOT NULL,
    description text,
    fields jsonb NOT NULL DEFAULT '[]',
    layout jsonb,
    version integer DEFAULT 1,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    created_by uuid
);

-- ============================================
-- 2. Partial unique index: one active schema per (org, type)
-- ============================================

CREATE UNIQUE INDEX IF NOT EXISTS idx_form_schemas_org_type_active
    ON public.form_schemas (organization_id, approval_type)
    WHERE is_active = true;

-- ============================================
-- 3. Additional indexes for common queries
-- ============================================

CREATE INDEX IF NOT EXISTS idx_form_schemas_org_id
    ON public.form_schemas (organization_id);

CREATE INDEX IF NOT EXISTS idx_form_schemas_approval_type
    ON public.form_schemas (approval_type);

-- ============================================
-- 4. Auto-update updated_at trigger
-- ============================================

CREATE OR REPLACE FUNCTION update_form_schemas_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_form_schemas_updated_at'
        AND tgrelid = 'public.form_schemas'::regclass
    ) THEN
        CREATE TRIGGER trg_form_schemas_updated_at
        BEFORE UPDATE ON public.form_schemas
        FOR EACH ROW
        EXECUTE FUNCTION update_form_schemas_updated_at();
    END IF;
EXCEPTION WHEN undefined_table THEN
    NULL;
END $$;

-- ============================================
-- 5. Enable RLS and create organization isolation policy
-- ============================================

ALTER TABLE public.form_schemas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Org Isolation for Form Schemas" ON public.form_schemas;
CREATE POLICY "Org Isolation for Form Schemas" ON public.form_schemas
    FOR ALL
    USING (
        organization_id = (
            SELECT organization_id
            FROM public.users
            WHERE id = auth.uid()
        )
    );

-- ============================================
-- 6. Grant permissions to authenticated users
-- ============================================

GRANT SELECT, INSERT, UPDATE, DELETE ON public.form_schemas TO authenticated;

-- ============================================
-- 7. Comments
-- ============================================

COMMENT ON TABLE public.form_schemas IS '自定义表单 Schema 定义表，按审批类型和组织隔离';
COMMENT ON COLUMN public.form_schemas.fields IS 'JSONB array of field definitions: [{key, label, type, required, options, min, max, ...}]';
COMMENT ON COLUMN public.form_schemas.layout IS 'Optional JSONB layout config for form grouping/sectioning';
COMMENT ON COLUMN public.form_schemas.approval_type IS 'The approval type this schema is associated with (e.g. expense, purchase, travel)';
