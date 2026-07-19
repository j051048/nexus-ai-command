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
}

export interface SolutionRequirement {
  id: string;
  title: string;
  priority: 'must' | 'should' | 'optional';
  status: 'open' | 'verified' | 'excluded';
  evidence_ref?: string | null;
}

export interface SolutionPackage {
  id: 'essential' | 'recommended' | 'advanced' | string;
  name: string;
  positioning: string;
  product_models: string[];
  components: string[];
  rationale: string;
  tradeoffs: string[];
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
}
