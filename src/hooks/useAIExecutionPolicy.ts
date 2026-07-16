import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

export type AIExecutionMode = 'economy' | 'balanced' | 'strict';

export interface AIExecutionPolicy {
  version: string;
  mode: AIExecutionMode;
  primary_model: string;
  embedding_model: string;
  rerank_model: string;
  premium_model: string | null;
  premium_manual_only: boolean;
  allow_llm_router: boolean;
  scheduled_primary_only: boolean;
  max_calls: number;
  max_verifications: number;
  max_iterations: number;
  max_input_tokens: number;
  max_output_tokens: number;
  max_task_cost_usd: number;
  max_latency_ms: number;
  context_tool_limit: number;
  retain_inference_receipts: boolean;
}

export interface AIServiceRole {
  code: 'chat' | 'embedding' | 'rerank' | 'premium';
  label: string;
  model: string | null;
  status: 'active' | 'manual_only' | 'disabled';
}

export interface AIServiceOverview {
  status: 'healthy' | 'degraded';
  policy_mode: AIExecutionMode;
  roles: AIServiceRole[];
  controls: {
    automatic_paid_routing: boolean;
    scheduled_primary_only: boolean;
    request_budget_enabled: boolean;
    receipt_retention: boolean;
  };
}

export interface PolicyWorker {
  code: string;
  label: string;
  capability: string;
  model: string;
  may_call_tools: boolean;
  readable_artifacts: string[];
  writable_artifacts: string[];
  max_calls: number;
  enabled: boolean;
}

export interface PolicySimulationCase {
  query: string;
  complexity?: string;
  scene_code?: string;
  agent_code?: string;
  requires_tools?: boolean;
  scheduled?: boolean;
}

export interface PolicySimulationResult {
  query: string;
  profile: {
    risk_level: 'low' | 'medium' | 'high';
    execution_depth: 'direct' | 'verify' | 'critic';
    reason_codes: string[];
    route_confidence: number;
  };
  policy: AIExecutionPolicy;
  planned_steps: string[];
  estimated_calls: number;
  estimated_latency_ms: number;
  model: string;
}

function unwrap<T>(response: { data?: { data?: T } | T }): T {
  const payload = response.data;
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return (payload as { data: T }).data;
  }
  return payload as T;
}

export function useAIExecutionPolicy() {
  return useQuery({
    queryKey: ['ai-execution-policy'],
    queryFn: async () => {
      const response = await httpClient.get('/api/llm/policy');
      return unwrap<{
        policy: AIExecutionPolicy;
        presets: Record<AIExecutionMode, AIExecutionPolicy>;
      }>(response);
    },
    staleTime: 60_000,
  });
}

export function useUpdateAIExecutionPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      mode: AIExecutionMode;
      retain_inference_receipts?: boolean;
    }) => {
      const response = await httpClient.put('/api/llm/policy', payload);
      return unwrap<AIExecutionPolicy>(response);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['ai-execution-policy'] }),
        queryClient.invalidateQueries({ queryKey: ['ai-service-overview'] }),
        queryClient.invalidateQueries({ queryKey: ['ai-policy-workers'] }),
      ]);
    },
  });
}

export function useAIServiceOverview() {
  return useQuery({
    queryKey: ['ai-service-overview'],
    queryFn: async () => {
      const response = await httpClient.get('/api/llm/service-overview');
      return unwrap<AIServiceOverview>(response);
    },
    staleTime: 60_000,
  });
}

export function usePolicyWorkers() {
  return useQuery({
    queryKey: ['ai-policy-workers'],
    queryFn: async () => {
      const response = await httpClient.get('/api/llm/policy/workers');
      return unwrap<PolicyWorker[]>(response);
    },
    staleTime: 60_000,
  });
}

export function useSimulateAIExecutionPolicy() {
  return useMutation({
    mutationFn: async (cases: PolicySimulationCase[]) => {
      const response = await httpClient.post('/api/llm/policy/simulate', { cases });
      return unwrap<PolicySimulationResult[]>(response);
    },
  });
}
