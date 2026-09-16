-- Deploy before the application. No data deletion or RLS disabling.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_user_org_id(p_user_id uuid)
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$ SELECT organization_id FROM public.users WHERE id = p_user_id $$;

CREATE OR REPLACE FUNCTION public.can_administer_members(p_org_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
 SELECT EXISTS (SELECT 1 FROM public.organization_members
   WHERE organization_id = p_org_id AND user_id = auth.uid()
     AND role IN ('admin', 'manager', 'boss', 'founder', 'owner'))
$$;
REVOKE ALL ON FUNCTION public.can_administer_members(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.can_administer_members(uuid) TO authenticated, service_role;

-- Replace this table's policy set as a unit: a leftover permissive policy can
-- both recurse and bypass the administrator-only membership write boundary.
DO $$ DECLARE p record; BEGIN
 FOR p IN SELECT policyname FROM pg_policies
   WHERE schemaname = 'public' AND tablename = 'organization_members'
 LOOP EXECUTE format('DROP POLICY %I ON public.organization_members', p.policyname); END LOOP;
END $$;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY member_read ON public.organization_members FOR SELECT TO authenticated
 USING (user_id = auth.uid() OR organization_id = public.get_user_org_id(auth.uid()));
CREATE POLICY member_insert ON public.organization_members FOR INSERT TO authenticated
 WITH CHECK (public.can_administer_members(organization_id));
CREATE POLICY member_update ON public.organization_members FOR UPDATE TO authenticated
 USING (public.can_administer_members(organization_id))
 WITH CHECK (public.can_administer_members(organization_id));
CREATE POLICY member_delete ON public.organization_members FOR DELETE TO authenticated
 USING (public.can_administer_members(organization_id));

ALTER TABLE public.agent_runs ADD COLUMN IF NOT EXISTS cost_usd numeric(14,6) NOT NULL DEFAULT 0;

-- A new, unambiguous RPC name avoids PostgREST's uuid/text overload resolution.
CREATE OR REPLACE FUNCTION public.upsert_daily_token_usage_v2(
 p_user_id uuid, p_org_id uuid, p_date date, p_tokens bigint, p_cost numeric,
 p_department_id text DEFAULT NULL, p_project_id text DEFAULT NULL
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$ DECLARE attribution public.user_token_usage%ROWTYPE; BEGIN
 IF p_tokens < 0 OR p_cost < 0 THEN RAISE EXCEPTION 'negative usage'; END IF;
 SELECT * INTO attribution FROM jsonb_populate_record(NULL::public.user_token_usage,
   jsonb_build_object('department_id', p_department_id, 'project_id', p_project_id));
 INSERT INTO public.user_token_usage(user_id, org_id, date, total_tokens,
   estimated_cost_usd, request_count, department_id, project_id)
 VALUES (p_user_id, p_org_id, p_date, COALESCE(p_tokens, 0), COALESCE(p_cost, 0),
   1, attribution.department_id, attribution.project_id)
 ON CONFLICT (user_id, date) DO UPDATE SET
   org_id = COALESCE(EXCLUDED.org_id, public.user_token_usage.org_id),
   total_tokens = public.user_token_usage.total_tokens + EXCLUDED.total_tokens,
   estimated_cost_usd = public.user_token_usage.estimated_cost_usd + EXCLUDED.estimated_cost_usd,
   request_count = public.user_token_usage.request_count + 1,
   department_id = COALESCE(EXCLUDED.department_id, public.user_token_usage.department_id),
   project_id = COALESCE(EXCLUDED.project_id, public.user_token_usage.project_id), updated_at = now();
END $$;
REVOKE ALL ON FUNCTION public.upsert_daily_token_usage_v2(uuid, uuid, date, bigint, numeric, text, text) FROM PUBLIC, authenticated, anon;
GRANT EXECUTE ON FUNCTION public.upsert_daily_token_usage_v2(uuid, uuid, date, bigint, numeric, text, text) TO service_role;

CREATE OR REPLACE FUNCTION public.enqueue_memory_persistence_job(p_job jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog
AS $$ DECLARE job_id uuid; BEGIN
 IF auth.uid() IS NULL OR auth.uid()::text IS DISTINCT FROM p_job->>'user_id'
   OR NOT EXISTS (SELECT 1 FROM public.organization_members m
       WHERE m.user_id = auth.uid() AND m.organization_id::text = p_job->>'organization_id')
   OR p_job->>'organization_id' IS DISTINCT FROM public.get_user_org_id(auth.uid())::text
 THEN RAISE EXCEPTION 'memory job identity mismatch' USING ERRCODE = '42501'; END IF;
 IF COALESCE(p_job->'payload'->>'ciphertext', '') = '' THEN
   RAISE EXCEPTION 'encrypted memory payload required'; END IF;
 INSERT INTO public.memory_persistence_jobs(organization_id, user_id, session_id, idempotency_key, payload, status)
 VALUES ((p_job->>'organization_id')::uuid, auth.uid(), p_job->>'session_id',
   p_job->>'idempotency_key', p_job->'payload', 'queued')
 ON CONFLICT (idempotency_key) DO NOTHING RETURNING id INTO job_id;
 IF job_id IS NULL THEN
   SELECT id INTO job_id FROM public.memory_persistence_jobs WHERE idempotency_key = p_job->>'idempotency_key'
     AND user_id = auth.uid() AND organization_id::text = p_job->>'organization_id';
 END IF;
 IF job_id IS NULL THEN RAISE EXCEPTION 'memory job conflict' USING ERRCODE = '42501'; END IF;
 RETURN job_id;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_memory_persistence_job(jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.enqueue_memory_persistence_job(jsonb) TO authenticated;

NOTIFY pgrst, 'reload schema';
COMMIT;
