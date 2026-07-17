import { useQuery } from "@tanstack/react-query";

import { httpClient } from "@/lib/httpClient";
import type { InstrumentLineCode } from "@/config/growthOperatingModel";

export type GrowthPriority = "urgent" | "high" | "medium" | "low";
export type GrowthRisk = "high" | "medium" | "low";

export interface GrowthMetrics {
  open_opportunities: number;
  pipeline_value: number;
  high_priority_signals: number;
  active_tasks: number;
  active_tenders: number;
  conversion_rate: number;
  classified_records: number;
}

export interface InstrumentDomainContext {
  domain_version: string;
  instrument_line_code?: InstrumentLineCode | null;
  instrument_line_name?: string;
  application_field?: string | null;
  product_models: string[];
  families?: string[];
  decision_roles?: string[];
  evidence_requirements?: string[];
  tender_focus?: string[];
  classification_status: "classified" | "unclassified";
}

export interface GrowthAction {
  id: string;
  priority: GrowthPriority;
  title: string;
  recommendation: string;
  reason: string;
  confidence: "high" | "medium";
  execution_mode: "recommend" | "confirm";
  target_url: string;
  source_signal_id: string;
  instrument_line_code?: InstrumentLineCode | null;
  instrument_line_name?: string;
  application_field?: string;
  domain_context: InstrumentDomainContext;
}

export interface GrowthSignal {
  id: string;
  kind: "market_signal" | "account_risk" | "tender_risk";
  priority: GrowthPriority;
  title: string;
  summary: string;
  source: string;
  source_label: string;
  evidence: string[];
  occurred_at?: string;
  target_url: string;
  estimated_value: number;
  instrument_line_code?: InstrumentLineCode | null;
  instrument_line_name?: string;
  application_field?: string;
  product_models: string[];
  domain_context: InstrumentDomainContext;
}

export interface GrowthAccount {
  id: string;
  name: string;
  contact_name?: string;
  industry?: string;
  stage: string;
  estimated_value: number;
  inactive_days?: number;
  risk: GrowthRisk;
  next_action: string;
  updated_at?: string;
  target_url: string;
  instrument_line_code?: InstrumentLineCode | null;
  instrument_line_name?: string;
  application_fields: string[];
  purchase_stage?: string;
  domain_context: InstrumentDomainContext;
}

export interface GrowthTender {
  id: string;
  name: string;
  client_name?: string;
  deadline?: string;
  days_left?: number;
  estimated_value: number;
  status: string;
  compliance_status: string;
  win_probability: number;
  risk: GrowthRisk;
  target_url: string;
  instrument_line_code?: InstrumentLineCode | null;
  instrument_line_name?: string;
  application_field?: string;
  target_product_models: string[];
  domain_context: InstrumentDomainContext;
}

export interface InstrumentLineSummary {
  code: InstrumentLineCode;
  name: string;
  signals: number;
  accounts: number;
  tenders: number;
  tasks: number;
}

export interface InstrumentLineDefinition {
  code: InstrumentLineCode;
  name: string;
  short_name: string;
  summary: string;
  families: string[];
  applications: string[];
  decision_roles: string[];
  evidence_requirements: string[];
  tender_focus: string[];
}

export interface GrowthReview {
  completed_growth_tasks: number;
  accepted_actions: number;
  completed_actions: number;
  action_adoption_rate: number;
  estimated_hours_saved: number;
  qualified_leads: number;
  wins: number;
  attributed_revenue: number;
  outcome_evidence_count: number;
  evidence_note: string;
}

export interface GrowthPlaybook {
  key: string;
  name: string;
  category: string;
  outcome: string;
  agents: string[];
  acceptance: string[];
  risk_policy: string;
}

export interface GrowthCapability {
  key: string;
  name: string;
  category: "signal" | "action" | "knowledge" | "connector";
  status: "ready" | "configurable" | "planned";
  risk_level: GrowthRisk;
  requires_confirmation: boolean;
  contract_version: string;
}

export interface GrowthWorkspace {
  schema_version: string;
  generated_at: string;
  metrics: GrowthMetrics;
  actions: GrowthAction[];
  signals: GrowthSignal[];
  accounts: GrowthAccount[];
  tenders: GrowthTender[];
  review: GrowthReview;
  context_graph: { nodes: number; links: number; entity_types: string[] };
  playbooks: GrowthPlaybook[];
  capabilities: GrowthCapability[];
  source_health: Record<string, "ready" | "degraded">;
  domain_catalog: {
    domain_version: string;
    instrument_lines: InstrumentLineDefinition[];
  };
  instrument_line_summary: InstrumentLineSummary[];
  sandbox: { enabled: boolean; data_isolation: string; production_data_mixed: boolean };
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export function useGrowthCommand() {
  return useQuery({
    queryKey: ["growth-command", "workspace", "v1"],
    queryFn: async () => {
      const response = await httpClient.get<ApiResponse<GrowthWorkspace>>(
        "/api/growth-command/workspace",
        { headers: { "X-Silent-Error": "1" } },
      );
      return response.data.data;
    },
    staleTime: 30_000,
    refetchInterval: 120_000,
    retry: 1,
  });
}
