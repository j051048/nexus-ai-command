-- P0-3: Performance Advisors 修复 — 为未索引的外键添加索引
-- 按高频查询表优先排序
CREATE TABLE IF NOT EXISTS public.user_token_usage (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL,
  org_id uuid,
  date date NOT NULL DEFAULT CURRENT_DATE,
  total_tokens bigint NOT NULL DEFAULT 0,
  estimated_cost_usd numeric(12,6) NOT NULL DEFAULT 0,
  request_count integer NOT NULL DEFAULT 0,
  department_id uuid,
  project_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, date)
);

ALTER TABLE public.user_token_usage ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 高频业务表
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customers_assigned_to ON public.customers(assigned_to);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customers_organization_id ON public.customers(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_activities_customer_id ON public.customer_activities(customer_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_activities_user_id ON public.customer_activities(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_customer_contacts_customer_id ON public.customer_contacts(customer_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_customer_id ON public.contracts(customer_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_organization_id ON public.contracts(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contracts_signed_by ON public.contracts(signed_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_events_contract_id ON public.contract_events(contract_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_events_user_id ON public.contract_events(user_id);

-- ============================================================================
-- Agent / AI 表
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_failure_logs_user_id ON public.agent_failure_logs(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_action_outcomes_org_id ON public.ai_action_outcomes(org_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_settings_org_id ON public.ai_settings(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_memories_org_id ON public.conversation_memories(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_graph_triples_user_id ON public.knowledge_graph_triples(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pending_confirmations_resolved_by ON public.pending_confirmations(resolved_by);

-- ============================================================================
-- 审批 / OA 表
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_approval_chains_org_id ON public.approval_chains(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_approval_requests_submitted_by ON public.approval_requests(submitted_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_approval_requests_on_behalf_of ON public.approval_requests(on_behalf_of);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_auto_approval_rules_created_by ON public.auto_approval_rules(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oa_leave_requests_approved_by ON public.oa_leave_requests(approved_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oa_leave_requests_handover_to ON public.oa_leave_requests(handover_to);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oa_tasks_created_by ON public.oa_tasks(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oa_tasks_project_id ON public.oa_tasks(project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oa_work_handovers_from_user ON public.oa_work_handovers(from_user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oa_work_handovers_to_user ON public.oa_work_handovers(to_user_id);

-- ============================================================================
-- HR / 人事表
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_candidates_job_position_id ON public.hr_candidates(job_position_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_candidates_referrer_id ON public.hr_candidates(referrer_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_employees_created_by ON public.hr_employees(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_employees_updated_by ON public.hr_employees(updated_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_job_positions_created_by ON public.hr_job_positions(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_performance_reviews_org_id ON public.hr_performance_reviews(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_performance_reviews_reviewer_id ON public.hr_performance_reviews(reviewer_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_performance_reviews_user_id ON public.hr_performance_reviews(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_hr_salary_records_org_id ON public.hr_salary_records(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_employees_position_id ON public.employees(position_id);

-- ============================================================================
-- 财务 / 销售表
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_expense_items_org_id ON public.expense_items(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_finance_budgets_project_id ON public.finance_budgets(project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_finance_expense_details_approval_id ON public.finance_expense_details(approval_request_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_finance_expense_details_project_id ON public.finance_expense_details(project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_finance_invoices_org_id ON public.finance_invoices(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_finance_invoices_user_id ON public.finance_invoices(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_leads_user_id ON public.sales_leads(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_metrics_org_id ON public.sales_metrics(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_metrics_user_id ON public.sales_metrics(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_targets_created_by ON public.sales_targets(created_by);

-- ============================================================================
-- 其他表
-- ============================================================================
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_created_by ON public.api_keys(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_org_id ON public.api_keys(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_usage_logs_api_key_id ON public.api_usage_logs(api_key_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_asset_transfers_from_user ON public.asset_transfers(from_user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_asset_transfers_to_user ON public.asset_transfers(to_user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_asset_transfers_operator ON public.asset_transfers(operator_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_attendance_records_org_id ON public.attendance_records(organization_id);
-- audit_logs was historically provisioned outside migrations in some
-- environments. Its canonical indexes are created after schema convergence.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backup_records_created_by ON public.backup_records(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_backup_records_org_id ON public.backup_records(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_badges_user_id ON public.badges(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitor_documents_doc_id ON public.competitor_documents(document_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitor_features_org_id ON public.competitor_features(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitor_products_org_id ON public.competitor_products(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_competitors_created_by ON public.competitors(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_org_id ON public.documents(org_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_parent_id ON public.documents(parent_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_im_user_mappings_user_id ON public.im_user_mappings(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_intent_rules_tenant_id ON public.intent_rules(tenant_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_inventory_transactions_operator ON public.inventory_transactions(operator_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_quota_config_tenant_id ON public.llm_quota_config(tenant_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_schedule_rule_backup ON public.llm_schedule_rule(backup_model_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_llm_schedule_rule_primary ON public.llm_schedule_rule(primary_model_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_org_id ON public.notifications(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_tokens_user_id ON public.oauth_tokens(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_project_timeline_project_id ON public.project_timeline(project_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_org_id ON public.projects(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_user_id ON public.projects(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_push_subscriptions_org_id ON public.push_subscriptions(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_schedules_last_report ON public.report_schedules(last_report_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_report_schedules_user_id ON public.report_schedules(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_security_events_org_id ON public.security_events(org_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_security_events_user_id ON public.security_events(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_shift_schedules_created_by ON public.shift_schedules(created_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_shift_schedules_shift_type ON public.shift_schedules(shift_type_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subscriptions_org_id ON public.subscriptions(org_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_training_progress_org_id ON public.training_progress(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_token_usage_org_id ON public.user_token_usage(org_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_org_id ON public.users(org_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vmd_reports_org_id ON public.vmd_reports(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_work_order_comments_user_id ON public.work_order_comments(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflow_shared_templates_org ON public.workflow_shared_templates(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflow_shared_templates_shared_by ON public.workflow_shared_templates(shared_by);
