export type SolutionStage =
  | 'brief'
  | 'requirements'
  | 'configuration'
  | 'draft'
  | 'review'
  | 'delivery';

export interface SolutionBrief {
  title: string;
  customer_id?: string | null;
  customer_name?: string;
  industry?: string;
  region?: string;
  budget_min?: number;
  budget_max?: number;
  instrument_line_code?: string;
  application_scenario?: string;
  deadline?: string;
  template_id?: string | null;
  scenario_pack_code?: string | null;
}

export interface SolutionRequirement {
  id: string;
  title: string;
  priority: 'must' | 'should' | 'optional';
  status: 'open' | 'verified' | 'excluded';
  evidence_ref?: string | null;
  source_document_id?: string | null;
  source_name?: string | null;
  source_excerpt?: string | null;
}

export interface SolutionCommercialSummary {
  currency?: string;
  list_price?: number | null;
  standard_cost?: number | null;
  gross_margin_percent?: number | null;
  lead_time_days?: number | null;
  warranty_months?: number | null;
  catalog_models?: number;
  validation_errors?: string[];
  validation_warnings?: string[];
  subtotal?: number;
  tax_rate?: number;
  tax?: number;
  total?: number;
  approval_required?: boolean;
  approval_reasons?: string[];
}

export interface SolutionQuoteLine {
  model_code: string;
  product_name?: string;
  category?: 'instrument' | 'accessory' | 'consumable' | 'software' | 'service';
  quantity: number;
  unit_price?: number;
  discount_percent?: number;
  net_unit_price?: number;
  line_total?: number;
  currency?: string;
}

export interface SolutionPackage {
  id: 'essential' | 'recommended' | 'advanced' | string;
  name: string;
  positioning: string;
  product_models: string[];
  components: string[];
  rationale: string;
  tradeoffs: string[];
  line_items?: SolutionQuoteLine[];
  commercial?: SolutionCommercialSummary;
}

export interface SolutionSection {
  id: string;
  title: string;
  content: string;
  evidence_refs: string[];
  status: 'draft' | 'review' | 'approved';
}

export interface SolutionReviewGate {
  id: string;
  label: string;
  passed: boolean;
}

export interface SolutionQuality {
  checks?: Record<string, boolean>;
  ready_for_external_use?: boolean;
  evidence_count?: number;
  open_claims?: number;
  completion?: number;
}

export interface SolutionWorkspaceState {
  schema_version: 'solution-workspace.v1';
  active_stage: SolutionStage;
  brief: SolutionBrief;
  requirements: SolutionRequirement[];
  packages: SolutionPackage[];
  sections: SolutionSection[];
  review_gates: SolutionReviewGate[];
  artifacts: Array<Record<string, unknown>>;
  generation: {
    generated_at?: string;
    model?: string;
    usage?: Record<string, number>;
    degraded?: boolean;
    knowledge_context_available?: boolean;
    cached?: boolean;
    duration_ms?: number;
    fingerprint?: string;
  };
  quality: SolutionQuality;
  extension_data: Record<string, unknown>;
}

export interface SolutionProject {
  id: string;
  project_code: string;
  title: string;
  customer_id?: string | null;
  customer_name?: string;
  industry?: string;
  region?: string;
  currency?: string;
  budget_min?: number;
  budget_max?: number;
  instrument_line_code?: string;
  application_scenario?: string;
  deadline?: string;
  status: string;
  current_version: number;
  workspace: SolutionWorkspaceState;
  outcome?: Record<string, unknown>;
  source_document_ids?: string[];
  linked_tender_project_id?: number | null;
  quality_evaluation?: SolutionEvaluation;
  bid_readiness?: TenderReadiness;
  updated_at?: string;
}

export interface SolutionVersionSummary {
  id: string;
  version_number: number;
  title: string;
  review_status: string;
  generation_metadata?: {
    generated_at?: string;
    model?: string;
    degraded?: boolean;
  };
  created_at?: string;
}

export interface SolutionVersionDetail extends SolutionVersionSummary {
  content: SolutionWorkspaceState;
  evidence_refs?: string[];
}

export interface SolutionCustomerOption {
  id: string;
  name: string;
  company?: string;
  industry?: string;
  instrument_line_code?: string;
  application_fields?: string[];
  purchase_stage?: string;
  budget_source?: string;
}

export interface SolutionProductOption {
  id?: string;
  instrument_line_code: string;
  product_name: string;
  model_code?: string;
  positioning?: string;
  application_fields?: string[];
  key_specs?: Record<string, unknown>;
  currency?: string;
  list_price?: number | null;
  standard_cost?: number | null;
  lead_time_days?: number | null;
  warranty_months?: number | null;
  lifecycle_status?: 'draft' | 'active' | 'limited' | 'eol';
  validation_status?: 'draft' | 'verified' | 'rejected';
  configuration_schema?: Record<string, unknown>;
  compatibility_rules?: Array<Record<string, unknown>>;
  service_items?: Array<Record<string, unknown> | string>;
  consumables?: Array<Record<string, unknown> | string>;
  evidence_refs?: Array<Record<string, unknown> | string>;
  is_active?: boolean;
}

export interface SolutionDocumentOption {
  id: string;
  name: string;
  doc_type?: string;
  status?: string;
  review_status?: 'pending' | 'verified' | 'rejected' | 'expired';
  source_version?: string | null;
  valid_until?: string | null;
  quality_score?: number | null;
  indexed_at?: string | null;
}

export interface SolutionTemplateOption {
  id: string;
  name: string;
  industry?: string;
  region?: string;
  instrument_line_code?: string;
  usage_count?: number;
  success_count?: number;
}

export interface SolutionContextOptions {
  customers: SolutionCustomerOption[];
  products: SolutionProductOption[];
  templates: SolutionTemplateOption[];
  documents: SolutionDocumentOption[];
  scenario_packs: SolutionScenarioPack[];
  capabilities?: {
    manage_catalog: boolean;
    view_cost: boolean;
    deliver_solution: boolean;
    manage_connectors: boolean;
  };
}

export interface SolutionScenarioPack {
  code: string;
  name: string;
  instrument_line_code: string;
  industry: string;
  required_facts: string[];
  section_outline: string[];
}

export interface SolutionEvaluation {
  evaluator_version: string;
  score: number;
  dimensions: Record<string, number>;
  findings: Array<{ severity: string; code: string; message: string }>;
  ready: boolean;
}

export interface TenderReadiness {
  score: number;
  decision: 'bid' | 'review' | 'no_bid';
  coverage_percent: number;
  major_deviations: number;
  deadline_days?: number | null;
  factors: Record<string, number>;
  deviations: Array<Record<string, unknown>>;
}

export interface SolutionReviewComment {
  id: string;
  section_id: string;
  content: string;
  status: 'open' | 'resolved';
  created_by?: string;
  created_at?: string;
}

export interface SolutionCPQPreview {
  quotes: Array<SolutionCommercialSummary & { package_id: string; line_items: SolutionQuoteLine[]; valid: boolean }>;
  valid: boolean;
  approval_required: boolean;
}

export interface SolutionCommercialApproval {
  id: string;
  project_id: string;
  package_id: string;
  quote_snapshot: Record<string, unknown>;
  reason?: string | null;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  requested_at?: string;
  decided_at?: string | null;
}

export interface SolutionAnalytics {
  projects: number;
  generated_projects: number;
  delivered_projects: number;
  won_projects: number;
  win_rate: number;
  average_readiness: number;
  feedback_events: number;
  acceptance_rate: number;
  delivery_events: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface SolutionConnector {
  id?: string;
  connector_code: string;
  display_name: string;
  connector_type: 'crm' | 'erp' | 'im' | 'storage' | 'email' | 'custom';
  status: 'disabled' | 'active' | 'error';
  capabilities: string[];
  last_health_at?: string | null;
}

export interface SolutionDeliveryEvent {
  id: string;
  project_id: string;
  channel: string;
  status: 'sent' | 'failed';
  artifact_name?: string;
  artifact_metadata?: Record<string, unknown>;
  created_at?: string;
}
