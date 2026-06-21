export type RuntimeTransitionReason =
  | 'user_prompt'
  | 'model_stream_started'
  | 'tool_use_detected'
  | 'tool_result_appended'
  | 'recovery_retry'
  | 'stop';

export interface AgentRuntimeLoopState {
  messagesCount: number;
  turnCount: number;
  transitionReason: RuntimeTransitionReason;
  pendingToolSummary?: string;
  compressionState: {
    stage: 'none' | 'snip' | 'micro' | 'collapse' | 'auto_compact';
    lastQualityScore: number;
    preserveEvidenceChain: boolean;
  };
}

export const AGENT_RUNTIME_LOOP_BLUEPRINT: AgentRuntimeLoopState = {
  messagesCount: 0,
  turnCount: 0,
  transitionReason: 'user_prompt',
  compressionState: {
    stage: 'none',
    lastQualityScore: 100,
    preserveEvidenceChain: true,
  },
};

export const TOOL_LIFECYCLE_V2_STAGES = [
  'discover',
  'load_schema',
  'validate_input',
  'classify_risk',
  'check_permission',
  'pre_tool_hook',
  'execute',
  'post_tool_hook',
  'render_result',
  'summarize_for_context',
] as const;

export const TOOL_LIFECYCLE_V2_POLICIES = [
  { toolType: 'read_only', concurrency: 'parallel', maxConcurrency: 10, requiresHitl: false },
  { toolType: 'draft_only', concurrency: 'parallel', maxConcurrency: 5, requiresHitl: false },
  { toolType: 'write', concurrency: 'serial', maxConcurrency: 1, requiresHitl: true },
  { toolType: 'external', concurrency: 'serial', maxConcurrency: 1, requiresHitl: true },
] as const;

export const DEFERRED_TOOL_SCHEMA_POLICY = {
  initialToolBudget: 12,
  fullSchemaLoadedBy: 'ToolSearch',
  alwaysLoadedTools: ['ToolSearch', 'ask_user', 'compact_context', 'query_action_inbox'],
  deferredGroups: ['crm_long_tail_tools', 'approval_admin_tools', 'document_export_tools', 'erp_integration_tools'],
} as const;

export const AGENT_RECOVERY_POLICIES = [
  { error: 'prompt_too_long', transition: 'staged_compact_retry', fallback: 'auto_compact_then_retry' },
  { error: 'tool_timeout', transition: 'retry_or_degrade', fallback: 'return_safe_partial_result' },
  { error: 'expensive_model_selected', transition: 'force_deepseek_v4_flash', fallback: 'deny_expensive_model_call' },
  { error: 'permission_denied', transition: 'ask_user_or_suggest_safe_draft', fallback: 'draft_only_no_side_effect' },
  { error: 'stream_broken', transition: 'resume_from_last_event', fallback: 'replay_last_stable_state' },
  { error: 'tool_result_too_large', transition: 'summarize_result_then_continue', fallback: 'attach_result_summary_only' },
] as const;

export const PROMPT_SECTION_REGISTRY = [
  { key: 'global_safety_rules', cacheScope: 'global', boundary: 'static' },
  { key: 'tenant_business_context', cacheScope: 'tenant', boundary: 'dynamic' },
  { key: 'session_memory', cacheScope: 'session', boundary: 'dynamic' },
  { key: 'turn_page_context', cacheScope: 'turn', boundary: 'uncached' },
] as const;

export const CONTEXT_COMPRESSION_PIPELINE = [
  { stage: 'snip', trigger: 'tool_result_over_budget' },
  { stage: 'micro', trigger: 'repeated_business_context' },
  { stage: 'collapse', trigger: 'context_above_70_percent' },
  { stage: 'auto_compact', trigger: 'context_above_90_percent' },
] as const;

export const PERMISSION_DECISION_V2_OUTCOMES = [
  { decision: 'allow', reasonType: 'rule', safeAlternative: null },
  { decision: 'ask', reasonType: 'hitl', safeAlternative: '先生成草稿或风险说明，不直接提交。' },
  { decision: 'deny', reasonType: 'field_policy', safeAlternative: '使用脱敏摘要或只读查询。' },
  { decision: 'passthrough', reasonType: 'hook', safeAlternative: '记录 hook 输出并等待下一步。' },
] as const;

export const SKILL_RUNTIME_MANIFESTS = [
  {
    key: 'scientific_instrument_bid_support',
    title: '科学仪器投标支持',
    contextMode: 'fork',
    defaultModel: 'deepseek-v4-flash',
    allowedTools: ['parse_tender_document', 'score_tender_response', 'fill_template'],
  },
  {
    key: 'customer_churn_recovery',
    title: '客户流失挽回',
    contextMode: 'inline',
    defaultModel: 'deepseek-v4-flash',
    allowedTools: ['score_customer_health', 'draft_followup', 'create_task'],
  },
  {
    key: 'approval_risk_review',
    title: '审批风控复核',
    contextMode: 'fork',
    defaultModel: 'deepseek-v4-flash',
    allowedTools: ['approval_risk_review', 'explain_policy'],
  },
  {
    key: 'weekly_business_report',
    title: 'AI 周报生成',
    contextMode: 'inline',
    defaultModel: 'deepseek-v4-flash',
    allowedTools: ['generate_customer_360', 'fill_template', 'export_audit_packet'],
  },
] as const;
