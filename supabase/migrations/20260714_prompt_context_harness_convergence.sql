-- Prompt / context / harness convergence.
-- The existing agent_prompt_versions table remains the canonical store; rich
-- artifact fields live in manifest to keep rolling deployments compatible.

UPDATE public.agent_prompt_versions
SET manifest = coalesce(manifest, '{}'::jsonb)
      || jsonb_build_object('legacy_status', status),
    status = CASE
      WHEN status IN ('deprecated', 'archived') THEN 'retired'
      ELSE 'draft'
    END,
    updated_at = now()
WHERE status NOT IN (
  'draft', 'linted', 'offline_eval', 'shadow', 'canary',
  'active', 'retired', 'rejected'
);

UPDATE public.agent_prompt_versions
SET status = 'retired', updated_at = now()
WHERE id IN (
  SELECT id
  FROM (
    SELECT id,
           row_number() OVER (
             PARTITION BY coalesce(organization_id::text, '__global__'), agent_code
             ORDER BY updated_at DESC, created_at DESC, id DESC
           ) AS position
    FROM public.agent_prompt_versions
    WHERE status = 'active'
  ) ranked
  WHERE ranked.position > 1
);

ALTER TABLE public.agent_prompt_versions
  DROP CONSTRAINT IF EXISTS agent_prompt_versions_status_check;

ALTER TABLE public.agent_prompt_versions
  ADD CONSTRAINT agent_prompt_versions_status_check CHECK (
    status IN (
      'draft', 'linted', 'offline_eval', 'shadow', 'canary',
      'active', 'retired', 'rejected'
    )
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_prompt_versions_active
  ON public.agent_prompt_versions (
    coalesce(organization_id::text, '__global__'),
    agent_code
  )
  WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_agent_prompt_versions_release
  ON public.agent_prompt_versions (
    organization_id,
    agent_code,
    status,
    updated_at DESC
  );

CREATE OR REPLACE FUNCTION public.transition_agent_prompt_artifact(
  p_version_id UUID,
  p_target_status TEXT,
  p_evidence JSONB DEFAULT '{}'::jsonb
)
RETURNS public.agent_prompt_versions
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
  current_row public.agent_prompt_versions%ROWTYPE;
  allowed_targets JSONB := jsonb_build_object(
    'draft', jsonb_build_array('linted', 'rejected'),
    'linted', jsonb_build_array('offline_eval', 'rejected'),
    'offline_eval', jsonb_build_array('shadow', 'rejected'),
    'shadow', jsonb_build_array('canary', 'rejected'),
    'canary', jsonb_build_array('active', 'rejected'),
    'active', jsonb_build_array('retired'),
    'retired', '[]'::jsonb,
    'rejected', jsonb_build_array('draft')
  );
  required_key TEXT;
BEGIN
  SELECT * INTO current_row
  FROM public.agent_prompt_versions
  WHERE id = p_version_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'prompt artifact not found: %', p_version_id;
  END IF;

  IF NOT coalesce(allowed_targets -> current_row.status, '[]'::jsonb) ? p_target_status THEN
    RAISE EXCEPTION 'invalid prompt transition: % -> %', current_row.status, p_target_status;
  END IF;

  IF p_target_status IN ('linted', 'offline_eval', 'shadow', 'canary', 'active') THEN
    FOREACH required_key IN ARRAY CASE p_target_status
      WHEN 'linted' THEN ARRAY['lint']
      WHEN 'offline_eval' THEN ARRAY['lint', 'offline_eval']
      WHEN 'shadow' THEN ARRAY['lint', 'offline_eval', 'shadow']
      ELSE ARRAY['lint', 'offline_eval', 'shadow', 'canary']
    END
    LOOP
      IF NOT (
        coalesce((p_evidence -> required_key ->> 'passed')::boolean, false)
        OR p_evidence -> required_key = 'true'::jsonb
      ) THEN
        RAISE EXCEPTION 'missing passing release evidence: %', required_key;
      END IF;
    END LOOP;
  END IF;

  IF p_target_status = 'active' THEN
    UPDATE public.agent_prompt_versions
    SET status = 'retired', updated_at = now()
    WHERE id <> current_row.id
      AND agent_code = current_row.agent_code
      AND organization_id IS NOT DISTINCT FROM current_row.organization_id
      AND status = 'active';
  END IF;

  UPDATE public.agent_prompt_versions
  SET status = p_target_status,
      manifest = coalesce(manifest, '{}'::jsonb)
        || jsonb_build_object(
          'evidence', coalesce(p_evidence, '{}'::jsonb),
          'transitioned_at', now()
        ),
      updated_at = now()
  WHERE id = current_row.id
  RETURNING * INTO current_row;

  RETURN current_row;
END;
$$;

COMMENT ON FUNCTION public.transition_agent_prompt_artifact(UUID, TEXT, JSONB)
IS 'Atomically advances a prompt artifact only when required release evidence passed.';
