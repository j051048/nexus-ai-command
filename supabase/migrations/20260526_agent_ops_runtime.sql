-- Aeon-inspired Agent Ops runtime persistence.

CREATE TABLE IF NOT EXISTS agent_heartbeat_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  status TEXT NOT NULL DEFAULT 'ok',
  summary TEXT,
  attention_items JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_skill_health (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  skill_key TEXT NOT NULL,
  score NUMERIC(4,2) NOT NULL DEFAULT 0,
  success_rate NUMERIC(6,4) NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  last_status TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id, skill_key)
);

CREATE TABLE IF NOT EXISTS agent_reactive_triggers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  trigger_key TEXT NOT NULL,
  condition_expr TEXT NOT NULL,
  run_target TEXT NOT NULL,
  autonomy TEXT NOT NULL DEFAULT 'proposal_only',
  risk TEXT NOT NULL DEFAULT 'medium',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id, trigger_key)
);

CREATE TABLE IF NOT EXISTS agent_chain_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  chain_key TEXT NOT NULL,
  focus_var TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  output_contract TEXT,
  outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_persona_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  persona_key TEXT NOT NULL,
  role_name TEXT NOT NULL,
  style_contract TEXT NOT NULL,
  must_do JSONB NOT NULL DEFAULT '[]'::jsonb,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id, persona_key)
);

CREATE TABLE IF NOT EXISTS agent_external_capabilities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID,
  capability_key TEXT NOT NULL,
  description TEXT,
  protocols JSONB NOT NULL DEFAULT '[]'::jsonb,
  risk TEXT NOT NULL DEFAULT 'low',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id, capability_key)
);

CREATE INDEX IF NOT EXISTS idx_agent_heartbeat_runs_org_created
  ON agent_heartbeat_runs(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_skill_health_org_score
  ON agent_skill_health(organization_id, score);
CREATE INDEX IF NOT EXISTS idx_agent_chain_runs_org_updated
  ON agent_chain_runs(organization_id, updated_at DESC);
