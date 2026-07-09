export interface NexusExecutionContextBlueprint {
  userId: string;
  organizationId: string;
  role: 'employee' | 'boss' | 'admin';
  locale: 'zh-CN';
  currency: 'CNY';
  defaultLlmModel: 'deepseek-v4-flash';
  monthlyLlmBudgetUsd: number;
  allowedApps: string[];
  featureFlags: string[];
}

export interface BusinessAppManifest {
  key: string;
  title: string;
  routes: string[];
  apis: string[];
  tables: string[];
  agentTools: string[];
  demoPack: string;
  qualityGates: string[];
}

export interface AIServerActionManifest {
  key: string;
  label: string;
  object: string;
  riskLevel: 'low' | 'medium' | 'high';
  requiresHitl: boolean;
  maxBatchSize: number;
  tools: string[];
  auditEvent: string;
}

export interface FieldPromptPolicy {
  model: string;
  field: string;
  classification: 'business_context' | 'personal_data' | 'commercial_sensitive' | 'financial_secret' | 'credential';
  promptVisibility: 'visible' | 'masked' | 'summary_only' | 'blocked';
  masking: 'none' | 'last4' | 'range_bucket' | 'never_send_to_llm';
}

export interface DocumentTemplateDefinition {
  key: string;
  title: string;
  sourceObjects: string[];
  outputFormats: string[];
  requiresHumanReview: boolean;
}

export const NEXUS_EXECUTION_CONTEXT_BLUEPRINT: NexusExecutionContextBlueprint = {
  userId: 'runtime-user',
  organizationId: 'runtime-organization',
  role: 'employee',
  locale: 'zh-CN',
  currency: 'CNY',
  defaultLlmModel: 'deepseek-v4-flash',
  monthlyLlmBudgetUsd: 20,
  allowedApps: ['action_inbox', 'crm', 'ai_operating_system', 'approval', 'knowledge'],
  featureFlags: ['ai_server_actions'],
};

export const BUSINESS_APP_MANIFESTS: BusinessAppManifest[] = [
  {
    key: 'action_inbox',
    title: '统一行动收件箱',
    routes: ['/inbox', '/dashboard'],
    apis: ['/api/inbox', '/api/action-events'],
    tables: ['action_events', 'notifications', 'approvals'],
    agentTools: ['summarize_actions', 'prioritize_next_best_action'],
    demoPack: 'first_week_action_pack',
    qualityGates: ['route_smoke', 'rls_policy', 'action_event_audit'],
  },
  {
    key: 'crm',
    title: '科学仪器 CRM',
    routes: ['/crm', '/sales'],
    apis: ['/api/crm', '/api/sales-leads'],
    tables: ['customers', 'contacts', 'sales_leads', 'action_events'],
    agentTools: ['score_customer_health', 'draft_followup', 'create_visit_note'],
    demoPack: 'scientific_instrument_crm_demo',
    qualityGates: ['tenant_isolation', 'customer_360_contract', 'crm_e2e'],
  },
  {
    key: 'ai_operating_system',
    title: '助手工作台',
    routes: ['/ai-operating-system', '/agent-improvement-center'],
    apis: ['/api/ai-operating-system'],
    tables: ['agent_runs', 'agent_ci_runs', 'agent_improvement_proposals'],
    agentTools: ['run_agent_simulation', 'define_agent_from_sop'],
    demoPack: 'agent_ops_demo',
    qualityGates: ['release_quality_gate', 'production_proof_gate'],
  },
  {
    key: 'approval',
    title: '审批与风控',
    routes: ['/approvals', '/approval-flows'],
    apis: ['/api/approvals', '/api/approval-flows'],
    tables: ['approvals', 'approval_flows', 'action_events'],
    agentTools: ['approval_risk_review', 'route_reviewer', 'explain_policy'],
    demoPack: 'approval_risk_demo',
    qualityGates: ['hitl_required', 'audit_log_immutable', 'approval_e2e'],
  },
  {
    key: 'document_template_center',
    title: '文档模板中心',
    routes: ['/documents', '/reports'],
    apis: ['/api/documents', '/api/reports'],
    tables: ['documents', 'reports', 'knowledge_chunks'],
    agentTools: ['fill_template', 'generate_customer_360', 'export_audit_packet'],
    demoPack: 'document_template_demo',
    qualityGates: ['template_render_contract', 'export_security_scan'],
  },
];

export const AI_SERVER_ACTIONS: AIServerActionManifest[] = [
  {
    key: 'crm.batch_followup_plan',
    label: '批量生成客户跟进计划',
    object: 'customer',
    riskLevel: 'low',
    requiresHitl: false,
    maxBatchSize: 50,
    tools: ['score_customer_health', 'draft_followup', 'create_task'],
    auditEvent: 'ai_server_action.crm_followup_plan',
  },
  {
    key: 'crm.batch_risk_score',
    label: '批量客户流失风险评分',
    object: 'customer',
    riskLevel: 'medium',
    requiresHitl: false,
    maxBatchSize: 100,
    tools: ['score_customer_health', 'build_evidence_pack'],
    auditEvent: 'ai_server_action.crm_risk_score',
  },
  {
    key: 'approval.bulk_risk_review',
    label: '批量审批风控复核',
    object: 'approval',
    riskLevel: 'high',
    requiresHitl: true,
    maxBatchSize: 20,
    tools: ['approval_risk_review', 'explain_policy'],
    auditEvent: 'ai_server_action.approval_bulk_risk_review',
  },
  {
    key: 'tender.generate_response_pack',
    label: '生成投标响应资料包',
    object: 'tender',
    riskLevel: 'high',
    requiresHitl: true,
    maxBatchSize: 5,
    tools: ['score_tender_response', 'generate_matrix', 'fill_template'],
    auditEvent: 'ai_server_action.tender_response_pack',
  },
];

export const FIELD_PROMPT_POLICIES: FieldPromptPolicy[] = [
  { model: 'customers', field: 'name', classification: 'business_context', promptVisibility: 'visible', masking: 'none' },
  { model: 'customers', field: 'phone', classification: 'personal_data', promptVisibility: 'masked', masking: 'last4' },
  { model: 'contracts', field: 'amount', classification: 'commercial_sensitive', promptVisibility: 'summary_only', masking: 'range_bucket' },
  { model: 'payments', field: 'bank_account', classification: 'financial_secret', promptVisibility: 'blocked', masking: 'never_send_to_llm' },
  { model: 'api_keys', field: 'secret', classification: 'credential', promptVisibility: 'blocked', masking: 'never_send_to_llm' },
];

export const DOCUMENT_TEMPLATE_CENTER: DocumentTemplateDefinition[] = [
  {
    key: 'customer_360_pdf',
    title: '客户 360 PDF',
    sourceObjects: ['customer', 'contact', 'project', 'contract', 'action_event'],
    outputFormats: ['pdf', 'docx'],
    requiresHumanReview: false,
  },
  {
    key: 'tender_scoring_matrix',
    title: '投标评分矩阵',
    sourceObjects: ['tender', 'document', 'competitor', 'knowledge_chunk'],
    outputFormats: ['xlsx', 'pdf'],
    requiresHumanReview: true,
  },
  {
    key: 'visit_note',
    title: '客户拜访纪要',
    sourceObjects: ['customer', 'contact', 'voice_memo', 'action_event'],
    outputFormats: ['docx', 'markdown'],
    requiresHumanReview: false,
  },
  {
    key: 'approval_audit_packet',
    title: '审批审计单',
    sourceObjects: ['approval', 'approval_flow', 'action_event', 'audit_log'],
    outputFormats: ['pdf', 'json'],
    requiresHumanReview: true,
  },
  {
    key: 'ai_value_weekly_report',
    title: 'AI 行为与价值周报',
    sourceObjects: ['agent_run', 'action_event', 'cost_event', 'trust_report'],
    outputFormats: ['pdf', 'html'],
    requiresHumanReview: false,
  },
];
