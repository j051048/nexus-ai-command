export type TenderStage =
  | 'intake'
  | 'review'
  | 'matrix'
  | 'draft'
  | 'quality'
  | 'delivery';

export type RequirementCategory =
  | 'mandatory'
  | 'technical'
  | 'commercial'
  | 'scoring'
  | 'delivery';

export type ResponseStatus = 'pending' | 'ready' | 'gap' | 'blocked';

export interface TenderRequirement {
  id: string;
  category: RequirementCategory;
  requirement: string;
  source_excerpt: string;
  response: string;
  evidence_ref: string;
  owner: string;
  status: ResponseStatus;
  ai_generated?: boolean;
}

export interface TenderDraftSection {
  id: string;
  title: string;
  purpose: string;
  status: 'not_started' | 'drafting' | 'ready' | 'approved';
  content?: string;
}

export interface TenderReviewGate {
  id: string;
  label: string;
  description: string;
  status: 'pending' | 'passed' | 'failed';
  required: boolean;
}

export interface TenderArtifact {
  id: string;
  name: string;
  kind: 'source' | 'analysis' | 'matrix' | 'draft' | 'delivery';
  status: 'working' | 'ready' | 'approved';
  document_id?: string;
  created_at: string;
}

export interface TenderWorkspaceState {
  schema_version: 'tender-workspace.v1';
  active_stage: TenderStage;
  source_document_id: string | null;
  source_document_name: string | null;
  requirements: TenderRequirement[];
  response_matrix: TenderRequirement[];
  draft_sections: TenderDraftSection[];
  review_gates: TenderReviewGate[];
  artifacts: TenderArtifact[];
  extension_data: Record<string, unknown>;
}

export interface TenderProject {
  id: number;
  project_code: string;
  project_name?: string;
  title?: string;
  client_name?: string;
  buyer_name?: string;
  deadline?: string;
  bid_deadline?: string;
  estimated_value?: number;
  status: string;
  compliance_status: string;
  win_probability?: number;
  instrument_line_code?: string;
  application_field?: string;
  target_product_models?: string[];
  update_time?: string;
  workspace: TenderWorkspaceState;
}

export interface TenderProjectInput {
  name: string;
  client_name?: string;
  deadline?: string;
  estimated_value?: number;
  instrument_line_code?: string;
  application_field?: string;
  target_product_models?: string[];
}
