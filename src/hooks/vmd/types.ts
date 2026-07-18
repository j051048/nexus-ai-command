import type { InstrumentLineCode } from '@/config/growthOperatingModel';

// API payloads are normalized at the hook boundary and can contain extension fields.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyData = Record<string, any>;

export interface VMDTask {
  id: string;
  task_code: string;
  title: string;
  description: string;
  scene_code: string;
  status: 'pending' | 'planning' | 'executing' | 'reviewing' | 'done' | 'failed';
  priority: 'low' | 'normal' | 'high' | 'urgent';
  progress: number;
  deadline: string | null;
  created_at: string;
  updated_at: string;
  instrument_line_code?: InstrumentLineCode | null;
  application_field?: string | null;
  target_product_models: string[];
  domain_context?: Record<string, unknown>;
  sub_tasks?: VMDSubTask[];
}

export interface VMDSubTask {
  id: string;
  task_id: string;
  agent_role: string;
  title: string;
  description: string;
  status: 'todo' | 'in_progress' | 'done';
  progress: number;
  human_notes: string | null;
  output: string | null;
  sort_order: number;
  assignee_id: string | null;
  assignee_name: string | null;
  weight: number;
  start_date: string | null;
  due_date: string | null;
  review_status: string | null;
  created_at: string;
}

export interface VMDAgent {
  id: string;
  agent_code: string;
  name: string;
  role_description: string;
  system_prompt: string;
  tool_whitelist: string[];
  scene_codes: string[];
  model_tier: string;
  is_active: boolean;
  icon: string;
}

export interface LLMModel {
  id: string;
  provider_type: string;
  model_code: string;
  model_name: string;
  api_base_url: string;
  api_key?: string;
  secret_key?: string;
  model_id: string;
  model_type: 'chat' | 'embedding';
  timeout_ms: number;
  max_tokens: number;
  context_window: number;
  supports_tools: boolean;
  supports_streaming: boolean;
  input_price: number;
  output_price: number;
  is_active: boolean;
  is_default: boolean;
}

export interface ScheduleRule {
  id: string;
  rule_name: string;
  scene_code: string;
  agent_code: string;
  primary_model: string;
  backup_model: string;
  strategy: string;
  complexity_tier: string | null;
  priority: number;
}

export interface AvailableModel {
  model_id: string;
  name: string;
  provider: string;
  provider_label: string;
  type: 'chat' | 'embedding';
  context_window: number;
  max_tokens: number;
  supports_tools: boolean;
  supports_streaming: boolean;
  input_price_per_1m: number;
  output_price_per_1m: number;
  tags: string[];
  already_added: boolean;
  has_metadata: boolean;
  available_from: string[];
}

export interface ModelCategory {
  name: string;
  icon: string;
  models: AvailableModel[];
}

export interface AvailableModelsResponse {
  categories: ModelCategory[];
  upstream_total: number;
  catalog_matched: number;
  already_added: number;
  upstream_providers: string[];
}

export interface VMDClue {
  id: string;
  company_name: string;
  title: string;
  source: string;
  level: 'A' | 'B' | 'C' | 'D';
  status: 'new' | 'following' | 'high_intent' | 'key_customer' | 'converted';
  amount: number | null;
  assigned_to: string | null;
  follow_ups: VMDFollowUp[];
  created_at: string;
  updated_at: string;
}

export interface VMDFollowUp {
  id: string;
  clue_id: string;
  content: string;
  created_at: string;
}

export interface BidProject {
  id: string;
  project_name: string;
  purchaser: string;
  deadline: string;
  amount: number | null;
  status: string;
  keywords: string[];
  created_at: string;
}

export interface ComplianceResult {
  id: string;
  content_snippet: string;
  category: string;
  severity: 'info' | 'warning' | 'error';
  matched_text: string;
  suggestion: string;
}

export interface ComplianceRule {
  id: string;
  code: string;
  name: string;
  category: string;
  severity: 'info' | 'warning' | 'error';
  is_active: boolean;
  pattern: string;
}

export interface ComplianceLog {
  id: string;
  source: string;
  total_issues: number;
  status: 'clean' | 'has_issues';
  created_at: string;
}

export interface VMDROIMetrics {
  completed_tasks: number;
  manual_hours_saved: number;
  labor_cost_saved_cny: number;
  ai_cost_cny: number;
  net_savings_cny: number;
  roi_percentage: number;
  automation_rate: number;
  budget_daily_usd: number;
  budget_monthly_usd: number;
  actual_monthly_usd: number;
  budget_utilization: number;
  scene_savings: Array<{
    scene: string;
    tasks: number;
    hours_saved: number;
    cost_saved_cny: number;
  }>;
}
