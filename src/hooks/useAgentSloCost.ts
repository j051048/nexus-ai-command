import { useQuery } from '@tanstack/react-query';
import { httpClient } from '@/lib/httpClient';

export interface AgentSloCostSummary {
  status: 'healthy' | 'breaching';
  window_days: number;
  targets: Record<string, number>;
  metrics: {
    agent_run_count: number;
    agent_success_rate: number;
    agent_p95_duration_ms: number;
    llm_call_count: number;
    llm_p95_latency_ms: number;
    total_cost_usd: number;
    total_tokens: number;
    expensive_model_share: number;
  };
  model_mix: Array<{ model_code: string; calls: number; cost_usd: number }>;
  violations: string[];
}

const fallbackSummary: AgentSloCostSummary = {
  status: 'healthy',
  window_days: 7,
  targets: {
    agent_success_rate_min: 0.99,
    agent_p95_duration_ms_max: 8000,
    llm_p95_latency_ms_max: 5000,
    expensive_model_share_max: 0.01,
    daily_cost_usd_max: 20,
  },
  metrics: {
    agent_run_count: 0,
    agent_success_rate: 1,
    agent_p95_duration_ms: 0,
    llm_call_count: 0,
    llm_p95_latency_ms: 0,
    total_cost_usd: 0,
    total_tokens: 0,
    expensive_model_share: 0,
  },
  model_mix: [],
  violations: [],
};

export function useAgentSloCost(days = 7) {
  return useQuery({
    queryKey: ['dashboard', 'agent-slo-cost', days],
    queryFn: async () => {
      const response = await httpClient.get('/api/dashboard/agent-slo-cost', {
        params: { days },
        silentError: true,
      });
      return (response.data?.data ?? response.data ?? fallbackSummary) as AgentSloCostSummary;
    },
    staleTime: 2 * 60 * 1000,
    retry: 1,
    placeholderData: fallbackSummary,
  });
}
