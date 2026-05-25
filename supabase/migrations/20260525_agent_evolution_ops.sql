-- Agent Evolution Ops: prompt versions, CI runs, proposals, context quality,
-- reward events, marketplace skills, red-team findings and trust reports.
-- NOTE: public.agent_eval_cases is intentionally not created here. It is owned
-- by 20260508_prompt_context_harness_eval_cases.sql and reconciled by
-- 20260525_agent_eval_cases_schema_reconcile.sql to avoid IF NOT EXISTS silently
-- preserving an incompatible pre-existing schema.

CREATE TABLE IF NOT EXISTS public.agent_prompt_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  agent_code TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  owner TEXT,
  scenario TEXT,
  risk_tier TEXT DEFAULT 'medium',
  status TEXT DEFAULT 'draft',
  manifest JSONB DEFAULT '{}'::jsonb,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (organization_id, agent_code, prompt_version)
);

CREATE TABLE IF NOT EXISTS public.agent_improvement_proposals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  proposal_key TEXT NOT NULL,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  rationale TEXT,
  proposed_patch JSONB DEFAULT '{}'::jsonb,
  risk_level TEXT DEFAULT 'medium',
  status TEXT DEFAULT 'proposed',
  gray_percentage INTEGER DEFAULT 0 CHECK (gray_percentage >= 0 AND gray_percentage <= 100),
  ci_result JSONB DEFAULT '{}'::jsonb,
  decided_by UUID,
  decided_at TIMESTAMPTZ,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (organization_id, proposal_key)
);

CREATE TABLE IF NOT EXISTS public.agent_ci_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  candidate_version TEXT,
  source TEXT DEFAULT 'manual',
  score NUMERIC DEFAULT 0,
  passed BOOLEAN DEFAULT false,
  behavior_diff JSONB DEFAULT '{}'::jsonb,
  result JSONB DEFAULT '{}'::jsonb,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.context_quality_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  agent_run_id UUID,
  provider TEXT,
  quality_score NUMERIC,
  permission_scope TEXT,
  evidence_ids JSONB DEFAULT '[]'::jsonb,
  conflict_flag BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_reward_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  source TEXT NOT NULL,
  source_id TEXT,
  reward_type TEXT NOT NULL,
  reward_score NUMERIC DEFAULT 0,
  business_value NUMERIC DEFAULT 0,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_skill_marketplace (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  skill_key TEXT NOT NULL,
  title TEXT NOT NULL,
  category TEXT,
  description TEXT,
  install_manifest JSONB DEFAULT '{}'::jsonb,
  status TEXT DEFAULT 'available',
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (organization_id, skill_key)
);

CREATE TABLE IF NOT EXISTS public.agent_redteam_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  scenario_key TEXT NOT NULL,
  attack_type TEXT NOT NULL,
  severity TEXT DEFAULT 'medium',
  status TEXT DEFAULT 'open',
  finding JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.agent_trust_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  report_period TEXT NOT NULL,
  report JSONB DEFAULT '{}'::jsonb,
  created_by UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_prompt_versions_org_agent
  ON public.agent_prompt_versions (organization_id, agent_code, status);
CREATE INDEX IF NOT EXISTS idx_agent_improvement_proposals_org_status
  ON public.agent_improvement_proposals (organization_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_ci_runs_org_created
  ON public.agent_ci_runs (organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reward_events_org_created
  ON public.agent_reward_events (organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_redteam_findings_org_status
  ON public.agent_redteam_findings (organization_id, status, severity);
