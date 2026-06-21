export const LOW_COST_DEFAULT_MODEL = 'deepseek-v4-flash';

export const EXPENSIVE_MODEL_DENYLIST = [
  'gemini-3.1-pro-preview',
  'gemini-3-flash-preview',
  'gemini-3-pro-preview',
  'gpt-5-pro',
] as const;

export const AGENT_OPERATIONAL_HARDENING_AREAS = [
  'runtime_v2_main_chain',
  'tool_lifecycle_v2_rollout',
  'deferred_tool_schema_runtime',
  'model_policy_enforcer',
  'context_compression_eval',
  'skill_runtime_activation',
  'agent_replay_behavior_eval',
  'memory_write_governance',
  'permission_decision_explainability',
  'agent_run_replay_debugger',
] as const;

export const RUNTIME_V2_MAIN_CHAIN_ADOPTION = [
  {
    chain: '/api/chat',
    entrypoint: 'chat_service -> agent.graph',
    requiredFields: ['transition_reason', 'compression_state', 'recovery_attempts', 'pending_tool_summary'],
  },
  {
    chain: 'LangGraph node_execute',
    entrypoint: 'app.agent.node_execute',
    requiredFields: ['tool_lifecycle_stage', 'permission_decision', 'tool_summary'],
  },
  {
    chain: 'SSE stream',
    entrypoint: 'app.agent.stream',
    requiredFields: ['runtime_transition_event', 'resume_cursor', 'last_stable_state'],
  },
] as const;

export const TOOL_LIFECYCLE_V2_ROLLOUT = [
  { phase: 'read_only_tools', toolTypes: ['read_only'], strategy: 'parallel execution with schema summary' },
  { phase: 'draft_tools', toolTypes: ['draft_only'], strategy: 'parallel draft generation with result renderer' },
  { phase: 'write_tools', toolTypes: ['write', 'external'], strategy: 'serial execution gated by HITL and audit event' },
] as const;

export const DEFERRED_TOOL_SCHEMA_RUNTIME = {
  defaultLoadedToolCount: 12,
  selectionInputs: ['user_intent', 'current_route', 'selected_records', 'role', 'enabled_apps'],
  toolSearchContract: {
    name: 'ToolSearch',
    returns: ['name', 'description', 'input_schema', 'risk_level', 'tool_type'],
    maxResults: 8,
  },
  successMetrics: ['tool_selection_accuracy', 'prompt_token_reduction', 'wrong_tool_rate'],
} as const;

export const MODEL_POLICY_ENFORCER = {
  defaultModel: LOW_COST_DEFAULT_MODEL,
  denylist: EXPENSIVE_MODEL_DENYLIST,
  scheduledTasksPolicy: 'force_low_cost_default',
  productionFallback: 'deny_expensive_model_call',
} as const;

export const CONTEXT_COMPRESSION_EVAL_CASES = [
  { case: 'long_customer_timeline', compressionStage: 'micro', mustPreserve: ['customer_id', 'last_contact_date', 'next_action', 'evidence_links'] },
  { case: 'large_tender_document', compressionStage: 'collapse', mustPreserve: ['score_rules', 'technical_requirements', 'risk_flags'] },
  { case: 'multi_step_approval', compressionStage: 'auto_compact', mustPreserve: ['approval_id', 'decision_history', 'hitl_status', 'blocked_reason'] },
] as const;

export const SKILL_RUNTIME_ACTIVATION_RULES = [
  { skill: 'scientific_instrument_bid_support', signals: ['tender', 'bid', '招标', '投标', '评分矩阵'], contextMode: 'fork' },
  { skill: 'customer_churn_recovery', signals: ['30天未跟进', '流失风险', '客户健康分下降', 'followup'], contextMode: 'inline' },
  { skill: 'approval_risk_review', signals: ['审批', '报销', '金额异常', '合规'], contextMode: 'fork' },
  { skill: 'weekly_business_report', signals: ['周报', '业务价值', 'Agent行为', 'report'], contextMode: 'inline' },
] as const;

export const AGENT_REPLAY_BEHAVIOR_EVALS = [
  { flow: 'crm_followup_replay', expectedPolicy: 'draft_only_or_low_risk_auto', expectedTools: ['score_customer_health', 'draft_followup'] },
  { flow: 'approval_risk_replay', expectedPolicy: 'hitl_required', expectedTools: ['approval_risk_review', 'explain_policy'] },
  { flow: 'tender_support_replay', expectedPolicy: 'human_review_before_export', expectedTools: ['parse_tender_document', 'score_tender_response', 'fill_template'] },
] as const;

export const MEMORY_WRITE_GOVERNANCE = [
  { memoryType: 'user_preference', writePolicy: 'allow_with_source', ttlDays: 365, requiresConfirmation: false },
  { memoryType: 'business_fact', writePolicy: 'allow_with_evidence', ttlDays: 180, requiresConfirmation: false },
  { memoryType: 'sensitive_personal_data', writePolicy: 'deny', ttlDays: 0, requiresConfirmation: true },
  { memoryType: 'credential_or_secret', writePolicy: 'deny', ttlDays: 0, requiresConfirmation: true },
] as const;

export const PERMISSION_DECISION_EXPLAINABILITY = [
  { decision: 'allow', visibleReason: '该操作符合角色权限、字段策略和当前工具风险等级。' },
  { decision: 'ask', visibleReason: '该操作会产生业务副作用，需要人工确认后继续。' },
  { decision: 'deny', visibleReason: '该操作命中了权限、字段或成本限制，已被阻止。' },
  { decision: 'passthrough', visibleReason: '该操作交由业务 Hook 或上游系统继续判定。' },
] as const;

export const AGENT_RUN_REPLAY_DEBUGGER_FIELDS = [
  'run_id',
  'prompt_sections',
  'selected_tools',
  'permission_decisions',
  'compression_events',
  'model_policy_decisions',
  'cost_estimate',
  'recovery_transitions',
  'final_answer',
] as const;
