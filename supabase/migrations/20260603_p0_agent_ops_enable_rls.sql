-- Enable RLS for Agent Evolution / Agent Ops tenant-scoped tables.
-- Policies are defined in the table-owning migrations; this backfill makes
-- the enforcement switch explicit so CI and fresh deployments stay aligned.

ALTER TABLE public.agent_chain_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_ci_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_external_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_heartbeat_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_improvement_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_persona_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_prompt_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_reactive_triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_redteam_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_reward_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_skill_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_skill_marketplace ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_trust_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.context_quality_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p0_agent_chain_runs_tenant_isolation ON public.agent_chain_runs;
CREATE POLICY p0_agent_chain_runs_tenant_isolation ON public.agent_chain_runs FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_ci_runs_tenant_isolation ON public.agent_ci_runs;
CREATE POLICY p0_agent_ci_runs_tenant_isolation ON public.agent_ci_runs FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_external_capabilities_tenant_isolation ON public.agent_external_capabilities;
CREATE POLICY p0_agent_external_capabilities_tenant_isolation ON public.agent_external_capabilities FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_heartbeat_runs_tenant_isolation ON public.agent_heartbeat_runs;
CREATE POLICY p0_agent_heartbeat_runs_tenant_isolation ON public.agent_heartbeat_runs FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_improvement_proposals_tenant_isolation ON public.agent_improvement_proposals;
CREATE POLICY p0_agent_improvement_proposals_tenant_isolation ON public.agent_improvement_proposals FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_persona_profiles_tenant_isolation ON public.agent_persona_profiles;
CREATE POLICY p0_agent_persona_profiles_tenant_isolation ON public.agent_persona_profiles FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_prompt_versions_tenant_isolation ON public.agent_prompt_versions;
CREATE POLICY p0_agent_prompt_versions_tenant_isolation ON public.agent_prompt_versions FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_reactive_triggers_tenant_isolation ON public.agent_reactive_triggers;
CREATE POLICY p0_agent_reactive_triggers_tenant_isolation ON public.agent_reactive_triggers FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_redteam_findings_tenant_isolation ON public.agent_redteam_findings;
CREATE POLICY p0_agent_redteam_findings_tenant_isolation ON public.agent_redteam_findings FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_reward_events_tenant_isolation ON public.agent_reward_events;
CREATE POLICY p0_agent_reward_events_tenant_isolation ON public.agent_reward_events FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_skill_health_tenant_isolation ON public.agent_skill_health;
CREATE POLICY p0_agent_skill_health_tenant_isolation ON public.agent_skill_health FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_skill_marketplace_tenant_isolation ON public.agent_skill_marketplace;
CREATE POLICY p0_agent_skill_marketplace_tenant_isolation ON public.agent_skill_marketplace FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_trust_reports_tenant_isolation ON public.agent_trust_reports;
CREATE POLICY p0_agent_trust_reports_tenant_isolation ON public.agent_trust_reports FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_context_quality_events_tenant_isolation ON public.context_quality_events;
CREATE POLICY p0_context_quality_events_tenant_isolation ON public.context_quality_events FOR ALL USING (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id IS NULL OR organization_id::text = public.current_tenant_id_text());
