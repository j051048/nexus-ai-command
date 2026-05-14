-- P0: Backfill tenant RLS policies for all tenant-scoped tables discovered by
-- the static migration scanner. Policies accept either the app.current_org_id
-- session setting used by server-side clients or the organization_id resolved
-- from Supabase auth.uid().

CREATE OR REPLACE FUNCTION public.current_tenant_id_text()
RETURNS text
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT COALESCE(
        NULLIF(current_setting('app.current_org_id', true), ''),
        (SELECT organization_id::text FROM public.users WHERE id = auth.uid())
    )
$$;

ALTER TABLE public.agent_failures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_scheduled_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_successes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_quality_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.llm_call_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.llm_usage_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sales_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tool_execution_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vmd_task_audit_record ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p0_agent_failures_tenant_isolation ON public.agent_failures;
CREATE POLICY p0_agent_failures_tenant_isolation ON public.agent_failures FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_goals_tenant_isolation ON public.agent_goals;
CREATE POLICY p0_agent_goals_tenant_isolation ON public.agent_goals FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_scheduled_tasks_tenant_isolation ON public.agent_scheduled_tasks;
CREATE POLICY p0_agent_scheduled_tasks_tenant_isolation ON public.agent_scheduled_tasks FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_successes_tenant_isolation ON public.agent_successes;
CREATE POLICY p0_agent_successes_tenant_isolation ON public.agent_successes FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_ai_quality_daily_tenant_isolation ON public.ai_quality_daily;
CREATE POLICY p0_ai_quality_daily_tenant_isolation ON public.ai_quality_daily FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_llm_call_log_tenant_isolation ON public.llm_call_log;
CREATE POLICY p0_llm_call_log_tenant_isolation ON public.llm_call_log FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_llm_usage_stats_tenant_isolation ON public.llm_usage_stats;
CREATE POLICY p0_llm_usage_stats_tenant_isolation ON public.llm_usage_stats FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_sales_targets_tenant_isolation ON public.sales_targets;
CREATE POLICY p0_sales_targets_tenant_isolation ON public.sales_targets FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_tool_execution_audit_tenant_isolation ON public.tool_execution_audit;
CREATE POLICY p0_tool_execution_audit_tenant_isolation ON public.tool_execution_audit FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_user_preferences_tenant_isolation ON public.user_preferences;
CREATE POLICY p0_user_preferences_tenant_isolation ON public.user_preferences FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_vmd_task_audit_record_tenant_isolation ON public.vmd_task_audit_record;
CREATE POLICY p0_vmd_task_audit_record_tenant_isolation ON public.vmd_task_audit_record FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());

DROP POLICY IF EXISTS p0_agent_eval_cases_tenant_isolation ON public.agent_eval_cases;
CREATE POLICY p0_agent_eval_cases_tenant_isolation ON public.agent_eval_cases FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_agent_failure_logs_tenant_isolation ON public.agent_failure_logs;
CREATE POLICY p0_agent_failure_logs_tenant_isolation ON public.agent_failure_logs FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_ai_roi_daily_tenant_isolation ON public.ai_roi_daily;
CREATE POLICY p0_ai_roi_daily_tenant_isolation ON public.ai_roi_daily FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_ai_settings_tenant_isolation ON public.ai_settings;
CREATE POLICY p0_ai_settings_tenant_isolation ON public.ai_settings FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_api_keys_tenant_isolation ON public.api_keys;
CREATE POLICY p0_api_keys_tenant_isolation ON public.api_keys FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_approval_chains_tenant_isolation ON public.approval_chains;
CREATE POLICY p0_approval_chains_tenant_isolation ON public.approval_chains FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_approval_requests_tenant_isolation ON public.approval_requests;
CREATE POLICY p0_approval_requests_tenant_isolation ON public.approval_requests FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_backup_records_tenant_isolation ON public.backup_records;
CREATE POLICY p0_backup_records_tenant_isolation ON public.backup_records FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_backup_schedules_tenant_isolation ON public.backup_schedules;
CREATE POLICY p0_backup_schedules_tenant_isolation ON public.backup_schedules FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_bid_project_tenant_isolation ON public.bid_project;
CREATE POLICY p0_bid_project_tenant_isolation ON public.bid_project FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_business_clue_tenant_isolation ON public.business_clue;
CREATE POLICY p0_business_clue_tenant_isolation ON public.business_clue FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_calendar_events_tenant_isolation ON public.calendar_events;
CREATE POLICY p0_calendar_events_tenant_isolation ON public.calendar_events FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_chat_messages_tenant_isolation ON public.chat_messages;
CREATE POLICY p0_chat_messages_tenant_isolation ON public.chat_messages FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_competitor_features_tenant_isolation ON public.competitor_features;
CREATE POLICY p0_competitor_features_tenant_isolation ON public.competitor_features FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_competitor_products_tenant_isolation ON public.competitor_products;
CREATE POLICY p0_competitor_products_tenant_isolation ON public.competitor_products FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_competitors_tenant_isolation ON public.competitors;
CREATE POLICY p0_competitors_tenant_isolation ON public.competitors FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_compliance_check_log_tenant_isolation ON public.compliance_check_log;
CREATE POLICY p0_compliance_check_log_tenant_isolation ON public.compliance_check_log FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_compliance_evidence_events_tenant_isolation ON public.compliance_evidence_events;
CREATE POLICY p0_compliance_evidence_events_tenant_isolation ON public.compliance_evidence_events FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_compliance_rule_tenant_isolation ON public.compliance_rule;
CREATE POLICY p0_compliance_rule_tenant_isolation ON public.compliance_rule FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_contracts_tenant_isolation ON public.contracts;
CREATE POLICY p0_contracts_tenant_isolation ON public.contracts FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_conversation_episodes_tenant_isolation ON public.conversation_episodes;
CREATE POLICY p0_conversation_episodes_tenant_isolation ON public.conversation_episodes FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_conversation_memories_tenant_isolation ON public.conversation_memories;
CREATE POLICY p0_conversation_memories_tenant_isolation ON public.conversation_memories FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_dashboard_configs_tenant_isolation ON public.dashboard_configs;
CREATE POLICY p0_dashboard_configs_tenant_isolation ON public.dashboard_configs FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_enterprise_sso_login_events_tenant_isolation ON public.enterprise_sso_login_events;
CREATE POLICY p0_enterprise_sso_login_events_tenant_isolation ON public.enterprise_sso_login_events FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_file_uploads_tenant_isolation ON public.file_uploads;
CREATE POLICY p0_file_uploads_tenant_isolation ON public.file_uploads FOR ALL USING (org_id::text = public.current_tenant_id_text()) WITH CHECK (org_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_finance_budgets_tenant_isolation ON public.finance_budgets;
CREATE POLICY p0_finance_budgets_tenant_isolation ON public.finance_budgets FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_hr_attendance_tenant_isolation ON public.hr_attendance;
CREATE POLICY p0_hr_attendance_tenant_isolation ON public.hr_attendance FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_hr_candidates_tenant_isolation ON public.hr_candidates;
CREATE POLICY p0_hr_candidates_tenant_isolation ON public.hr_candidates FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_hr_employees_tenant_isolation ON public.hr_employees;
CREATE POLICY p0_hr_employees_tenant_isolation ON public.hr_employees FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_hr_job_positions_tenant_isolation ON public.hr_job_positions;
CREATE POLICY p0_hr_job_positions_tenant_isolation ON public.hr_job_positions FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_hr_performance_reviews_tenant_isolation ON public.hr_performance_reviews;
CREATE POLICY p0_hr_performance_reviews_tenant_isolation ON public.hr_performance_reviews FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_hr_salary_records_tenant_isolation ON public.hr_salary_records;
CREATE POLICY p0_hr_salary_records_tenant_isolation ON public.hr_salary_records FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_installed_plugins_tenant_isolation ON public.installed_plugins;
CREATE POLICY p0_installed_plugins_tenant_isolation ON public.installed_plugins FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_integration_config_tenant_isolation ON public.integration_config;
CREATE POLICY p0_integration_config_tenant_isolation ON public.integration_config FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_knowledge_graph_triples_tenant_isolation ON public.knowledge_graph_triples;
CREATE POLICY p0_knowledge_graph_triples_tenant_isolation ON public.knowledge_graph_triples FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_knowledge_library_tenant_isolation ON public.knowledge_library;
CREATE POLICY p0_knowledge_library_tenant_isolation ON public.knowledge_library FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_llm_model_config_tenant_isolation ON public.llm_model_config;
CREATE POLICY p0_llm_model_config_tenant_isolation ON public.llm_model_config FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_llm_quota_config_tenant_isolation ON public.llm_quota_config;
CREATE POLICY p0_llm_quota_config_tenant_isolation ON public.llm_quota_config FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_llm_schedule_rule_tenant_isolation ON public.llm_schedule_rule;
CREATE POLICY p0_llm_schedule_rule_tenant_isolation ON public.llm_schedule_rule FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_notifications_tenant_isolation ON public.notifications;
CREATE POLICY p0_notifications_tenant_isolation ON public.notifications FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_oa_leave_requests_tenant_isolation ON public.oa_leave_requests;
CREATE POLICY p0_oa_leave_requests_tenant_isolation ON public.oa_leave_requests FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_oa_meeting_bookings_tenant_isolation ON public.oa_meeting_bookings;
CREATE POLICY p0_oa_meeting_bookings_tenant_isolation ON public.oa_meeting_bookings FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_oa_meeting_rooms_tenant_isolation ON public.oa_meeting_rooms;
CREATE POLICY p0_oa_meeting_rooms_tenant_isolation ON public.oa_meeting_rooms FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_oa_tasks_tenant_isolation ON public.oa_tasks;
CREATE POLICY p0_oa_tasks_tenant_isolation ON public.oa_tasks FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_oa_work_handovers_tenant_isolation ON public.oa_work_handovers;
CREATE POLICY p0_oa_work_handovers_tenant_isolation ON public.oa_work_handovers FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_org_memories_tenant_isolation ON public.org_memories;
CREATE POLICY p0_org_memories_tenant_isolation ON public.org_memories FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_profiles_tenant_isolation ON public.profiles;
CREATE POLICY p0_profiles_tenant_isolation ON public.profiles FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_projects_tenant_isolation ON public.projects;
CREATE POLICY p0_projects_tenant_isolation ON public.projects FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_push_subscriptions_tenant_isolation ON public.push_subscriptions;
CREATE POLICY p0_push_subscriptions_tenant_isolation ON public.push_subscriptions FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_report_schedules_tenant_isolation ON public.report_schedules;
CREATE POLICY p0_report_schedules_tenant_isolation ON public.report_schedules FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_saved_reports_tenant_isolation ON public.saved_reports;
CREATE POLICY p0_saved_reports_tenant_isolation ON public.saved_reports FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_training_progress_tenant_isolation ON public.training_progress;
CREATE POLICY p0_training_progress_tenant_isolation ON public.training_progress FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_user_scheduled_tasks_tenant_isolation ON public.user_scheduled_tasks;
CREATE POLICY p0_user_scheduled_tasks_tenant_isolation ON public.user_scheduled_tasks FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_vmd_agent_config_tenant_isolation ON public.vmd_agent_config;
CREATE POLICY p0_vmd_agent_config_tenant_isolation ON public.vmd_agent_config FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_vmd_main_task_tenant_isolation ON public.vmd_main_task;
CREATE POLICY p0_vmd_main_task_tenant_isolation ON public.vmd_main_task FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_vmd_sub_task_tenant_isolation ON public.vmd_sub_task;
CREATE POLICY p0_vmd_sub_task_tenant_isolation ON public.vmd_sub_task FOR ALL USING (tenant_id::text = public.current_tenant_id_text()) WITH CHECK (tenant_id::text = public.current_tenant_id_text());
DROP POLICY IF EXISTS p0_workflow_shared_templates_tenant_isolation ON public.workflow_shared_templates;
CREATE POLICY p0_workflow_shared_templates_tenant_isolation ON public.workflow_shared_templates FOR ALL USING (organization_id::text = public.current_tenant_id_text()) WITH CHECK (organization_id::text = public.current_tenant_id_text());
