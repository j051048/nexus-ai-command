import { useMutation, useQuery } from '@tanstack/react-query';
import { httpClient } from '@/lib/httpClient';

export interface BusinessGraphNode {
  id: string;
  type: string;
  label: string;
  status?: string | null;
  value?: number | string | null;
  updated_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface BusinessGraphEdge {
  source: string;
  target: string;
  label: string;
  strength: number;
}

export interface BusinessContextGraph {
  nodes: BusinessGraphNode[];
  edges: BusinessGraphEdge[];
  summary: {
    node_count: number;
    edge_count: number;
    density: number;
    entity_counts: Record<string, number>;
  };
  prompt_context: string;
}

export interface AIOperatingOverview {
  window_days: number;
  agent: {
    total_runs: number;
    completed: number;
    failed: number;
    failure_rate: number;
    success_rate: number;
    tool_failure_signals: number;
    total_cost_usd: number;
    total_tokens: number;
  };
  actions: {
    total_events: number;
    accepted: number;
    completed: number;
    ignored: number;
    completion_rate: number;
    acceptance_rate: number;
  };
  graph: BusinessContextGraph;
  recent_runs: Array<{
    id?: string;
    run_id?: string;
    status?: string;
    input_summary?: string;
    updated_at?: string;
  }>;
  operating_metrics: {
    agent_success_rate: number;
    action_completion_rate: number;
    context_graph_nodes: number;
    context_graph_edges: number;
  };
  value: {
    saved_minutes: number;
    saved_hours: number;
    automated_followups: number;
    risk_reviews: number;
    estimated_value_cny: number;
    roi_story: string;
  };
  trust: {
    confidence_score: number;
    confidence_level: string;
    human_review_rate: number;
    tool_failure_rate: number;
    audit_summary: string;
  };
}

export interface AgentSimulationPayload {
  messages: string[];
  baseline_policy?: string;
  candidate_policy?: string;
}

export interface AgentSimulationResult {
  cases: Array<{
    id: string;
    message: string;
    detected_intent: string;
    suggested_tools: string[];
    baseline: { mode: string; expected_outcome: string };
    candidate: { mode: string; policy: string; expected_outcome: string };
    risk_score: number;
    risk_flags: string[];
  }>;
  summary: {
    case_count: number;
    automation_rate: number;
    hitl_rate: number;
    avg_risk_score: number;
    recommendation: string;
  };
  context_graph_summary: BusinessContextGraph['summary'];
  baseline_policy: string;
  candidate_policy: string;
}

export interface AgentDefinitionPayload {
  sop_text: string;
  scenario?: string;
  autonomy_level?: string;
}

export interface AgentDefinitionResult {
  scenario: string;
  autonomy_level: string;
  intent_rules: Array<{
    name: string;
    trigger: string;
    tools: string[];
    autonomy: string;
  }>;
  operating_procedure: Array<{
    step: number;
    name: string;
    instruction: string;
    expected_evidence: string;
  }>;
  tools: string[];
  guardrails: string[];
  test_cases: string[];
  confidence: number;
  next_steps: string[];
  definition_markdown: string;
}

export function useAIOperatingOverview(days = 30) {
  return useQuery({
    queryKey: ['ai-operating-system-overview', days],
    queryFn: async () => {
      const response = await httpClient.get('/api/ai-operating-system/overview', {
        params: { days },
      });
      return response.data?.data as AIOperatingOverview;
    },
    refetchInterval: 180_000,
    retry: 1,
  });
}

export function useRunAgentSimulation() {
  return useMutation({
    mutationFn: async (payload: AgentSimulationPayload) => {
      const response = await httpClient.post('/api/ai-operating-system/simulate', payload);
      return response.data?.data as AgentSimulationResult;
    },
  });
}

export function useDefineAgentFromSop() {
  return useMutation({
    mutationFn: async (payload: AgentDefinitionPayload) => {
      const response = await httpClient.post('/api/ai-operating-system/define-agent', payload);
      return response.data?.data as AgentDefinitionResult;
    },
  });
}
