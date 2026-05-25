-- Reconcile agent_eval_cases after older deployments created incompatible
-- variants (for example org_id/criticality/query) before the prompt/context
-- harness schema settled on organization_id/dimension/input_json.
-- schema-conflict-scan: allow-reconcile-create

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'agent_eval_cases'
  ) THEN
    CREATE TABLE public.agent_eval_cases (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      organization_id uuid NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
      source_type text NOT NULL,
      source_ref text NOT NULL,
      status text NOT NULL DEFAULT 'pending_label',
      dimension text NOT NULL DEFAULT 'task_completion',
      input_json jsonb NOT NULL DEFAULT '{}'::jsonb,
      expected_json jsonb NOT NULL DEFAULT '{}'::jsonb,
      metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
      labelled_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
      labelled_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

ALTER TABLE public.agent_eval_cases
  ADD COLUMN IF NOT EXISTS organization_id uuid,
  ADD COLUMN IF NOT EXISTS source_type text,
  ADD COLUMN IF NOT EXISTS source_ref text,
  ADD COLUMN IF NOT EXISTS status text DEFAULT 'pending_label',
  ADD COLUMN IF NOT EXISTS dimension text DEFAULT 'task_completion',
  ADD COLUMN IF NOT EXISTS input_json jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS expected_json jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS metadata_json jsonb DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS labelled_by uuid,
  ADD COLUMN IF NOT EXISTS labelled_at timestamptz,
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'agent_eval_cases'
      AND column_name = 'org_id'
  ) THEN
    EXECUTE 'UPDATE public.agent_eval_cases SET organization_id = COALESCE(organization_id, org_id)';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'agent_eval_cases'
      AND column_name = 'criticality'
  ) THEN
    EXECUTE $sql$
      UPDATE public.agent_eval_cases
      SET metadata_json = COALESCE(metadata_json, '{}'::jsonb)
        || jsonb_build_object('criticality', criticality)
      WHERE criticality IS NOT NULL
    $sql$;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'agent_eval_cases'
      AND column_name = 'query'
  ) THEN
    EXECUTE $sql$
      UPDATE public.agent_eval_cases
      SET input_json = CASE
        WHEN input_json IS NULL OR input_json = '{}'::jsonb
          THEN jsonb_build_object('query', query)
        ELSE input_json || jsonb_build_object('query', query)
      END
      WHERE query IS NOT NULL
    $sql$;
  END IF;
END $$;

UPDATE public.agent_eval_cases
SET
  source_type = COALESCE(NULLIF(source_type, ''), 'legacy_agent_eval_case'),
  source_ref = COALESCE(NULLIF(source_ref, ''), id::text),
  status = COALESCE(NULLIF(status, ''), 'pending_label'),
  dimension = COALESCE(NULLIF(dimension, ''), 'task_completion'),
  input_json = COALESCE(input_json, '{}'::jsonb),
  expected_json = COALESCE(expected_json, '{}'::jsonb),
  metadata_json = COALESCE(metadata_json, '{}'::jsonb),
  created_at = COALESCE(created_at, now()),
  updated_at = COALESCE(updated_at, now());

ALTER TABLE public.agent_eval_cases
  ALTER COLUMN source_type SET NOT NULL,
  ALTER COLUMN source_ref SET NOT NULL,
  ALTER COLUMN status SET NOT NULL,
  ALTER COLUMN dimension SET NOT NULL,
  ALTER COLUMN input_json SET NOT NULL,
  ALTER COLUMN expected_json SET NOT NULL,
  ALTER COLUMN metadata_json SET NOT NULL,
  ALTER COLUMN created_at SET NOT NULL,
  ALTER COLUMN updated_at SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_eval_cases_source_unique
  ON public.agent_eval_cases (source_type, source_ref);

CREATE INDEX IF NOT EXISTS idx_agent_eval_cases_org_status
  ON public.agent_eval_cases (organization_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_eval_cases_dimension
  ON public.agent_eval_cases (dimension, status);

ALTER TABLE public.agent_eval_cases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p0_agent_eval_cases_tenant_isolation ON public.agent_eval_cases;
DROP POLICY IF EXISTS org_members_view_agent_eval_cases ON public.agent_eval_cases;
DROP POLICY IF EXISTS org_admins_manage_agent_eval_cases ON public.agent_eval_cases;
DROP POLICY IF EXISTS "org_members_view_agent_eval_cases" ON public.agent_eval_cases;
DROP POLICY IF EXISTS "org_admins_manage_agent_eval_cases" ON public.agent_eval_cases;

CREATE POLICY agent_eval_cases_tenant_read
ON public.agent_eval_cases
FOR SELECT
USING (
  organization_id IS NULL
  OR organization_id::text = public.current_tenant_id_text()
);

CREATE POLICY agent_eval_cases_tenant_write
ON public.agent_eval_cases
FOR ALL
USING (
  organization_id IS NULL
  OR organization_id::text = public.current_tenant_id_text()
)
WITH CHECK (
  organization_id IS NULL
  OR organization_id::text = public.current_tenant_id_text()
);
