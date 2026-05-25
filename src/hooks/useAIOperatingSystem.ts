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
