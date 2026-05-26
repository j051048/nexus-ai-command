import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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

export interface PromptManifest {
  agent_code: string;
  prompt_version: string;
  owner: string;
  scenario: string;
  risk_tier: string;
  status: string;
  eval_gates: string[];
  blocks: Array<{ name: string; purpose: string; risk: string; required: boolean }>;
}

export interface AgentCIResult {
  passed: boolean;
  score: number;
  case_count: number;
  recommendation: string;
  cases: Array<{
    id: string;
    message: string;
    passed: boolean;
    score: number;
    behavior_diff: {
      expected_tools: string[];
      actual_tools: string[];
      missing_tools: string[];
      forbidden_hits: string[];
    };
  }>;
}

export interface AgentImprovementProposalResult {
  proposals: Array<{
    id: string;
    category: string;
    title: string;
    rationale: string;
    proposed_patch: Record<string, unknown>;
    risk_level: string;
    approval_required: boolean;
    status: string;
  }>;
  agent_ci: AgentCIResult;
  governance: {
    self_mutation_allowed: boolean;
    required_flow: string[];
  };
}

export interface MemoryHygieneResult {
  sample_size: number;
  hygiene_score: number;
  stale_memories: number;
  expired_memories: number;
  compressed_memories: number;
  conflict_candidates: number;
  golden_examples: number;
  recommendations: string[];
  policy: Record<string, number>;
}

export interface AgentEvolutionOpsResult {
  generated_at: string;
  persistence: {
    migration: string;
    tables: string[];
    persisted_counts: Record<string, number>;
    mode: string;
  };
  proposal_flow: {
    states: string[];
    requires_human_approval: boolean;
    records: Array<{
      id: string;
      title: string;
      status: string;
      approval_required: boolean;
      gray_percentage: number;
      rollback_plan: string;
      allowed_actions: string[];
    }>;
  };
  diffs: {
    prompt_diff: Record<string, unknown>;
    context_diff: Record<string, unknown>;
    tool_diff: Record<string, unknown>;
  };
  low_quality_queue: Array<{
    id: string;
    reason: string;
    priority: string;
    suggested_action: string;
    source: string;
  }>;
  eval_dataset: {
    case_count: number;
    from_real_runs: number;
    coverage_dimensions: string[];
    cases: Array<Record<string, unknown>>;
  };
  reward_model: {
    name: string;
    score: number;
    signals: Array<{ name: string; weight: number }>;
    business_outcomes: string[];
  };
  skill_marketplace: Array<{
    id: string;
    name: string;
    scenario: string;
    agent_roles: string[];
    tools: string[];
    install_state: string;
    quality_gate: string;
  }>;
  multi_agent_protocol: {
    name: string;
    version: string;
    handoff_contract: string[];
    flows: Array<{ id: string; steps: Array<{ agent: string; responsibility: string }> }>;
  };
  redteam_center: {
    scenario_count: number;
    open_high: number;
    scenarios: Array<Record<string, string>>;
    latest_findings: Array<Record<string, unknown>>;
    required_release_gate: string;
  };
  trust_center: {
    customer_visible: boolean;
    confidence_score: number;
    confidence_level: string;
    audit_story: string;
    controls: string[];
  };
}

export interface AeonInspiredOpsResult {
  generated_at: string;
  inspiration: string;
  tables: string[];
  heartbeat: {
    status: string;
    checked_at: string;
    summary: string;
    notify_operator: boolean;
    attention_items: Array<Record<string, unknown>>;
  };
  skill_health: Array<{
    skill: string;
    window: number;
    score: number;
    success_rate: number;
    failure_count: number;
    flags: string[];
    last_status: string;
    recommended_action: string;
  }>;
  reactive_triggers: {
    trigger_count: number;
    definitions: Array<Record<string, unknown>>;
    fired: Array<Record<string, unknown>>;
    dsl: string;
  };
  self_repair: {
    mode: string;
    auto_apply: boolean;
    proposal_count: number;
    proposals: Array<Record<string, unknown>>;
  };
  skill_chains: {
    chain_count: number;
    chains: Array<{ id: string; var: string; steps: string[]; output_contract: string }>;
  };
  universal_var: {
    name: string;
    value: string;
    description: string;
    examples: string[];
    routing_hint: string;
  };
  operating_memory: {
    stores: string[];
    run_count: number;
    event_count: number;
    retention_policy: string;
    memory_promotion_rule: string;
  };
  instance_fleet: {
    instances: Array<Record<string, unknown>>;
    fleet_control: string;
  };
  persona_soul: {
    profiles: Array<Record<string, unknown>>;
    style_contract: string;
    guardrail: string;
  };
  external_capabilities: {
    gateway: string;
    capabilities: Array<Record<string, unknown>>;
    auth_boundary: string;
  };
  governance: {
    proposal_count: number;
    self_mutation_allowed: boolean;
    required_release_flow: string[];
  };
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

export function usePromptRegistry() {
  return useQuery({
    queryKey: ['ai-operating-system-prompt-registry'],
    queryFn: async () => {
      const response = await httpClient.get('/api/ai-operating-system/prompt-registry');
      return response.data?.data?.manifests as PromptManifest[];
    },
    retry: 1,
  });
}

export function useAgentCI() {
  return useMutation({
    mutationFn: async (payload: { cases?: unknown[]; candidate_metadata?: Record<string, unknown> } = {}) => {
      const response = await httpClient.post('/api/ai-operating-system/agent-ci', payload);
      return response.data?.data as AgentCIResult;
    },
  });
}

export function useAgentImprovementProposals() {
  return useQuery({
    queryKey: ['ai-operating-system-improvement-proposals'],
    queryFn: async () => {
      const response = await httpClient.get('/api/ai-operating-system/improvement-proposals');
      return response.data?.data as AgentImprovementProposalResult;
    },
    retry: 1,
  });
}

export function useMemoryHygiene() {
  return useQuery({
    queryKey: ['ai-operating-system-memory-hygiene'],
    queryFn: async () => {
      const response = await httpClient.get('/api/ai-operating-system/memory-hygiene');
      return response.data?.data as MemoryHygieneResult;
    },
    retry: 1,
  });
}

export function useAgentEvolutionOps() {
  return useQuery({
    queryKey: ['ai-operating-system-evolution-ops'],
    queryFn: async () => {
      const response = await httpClient.get('/api/ai-operating-system/evolution-ops');
      return response.data?.data as AgentEvolutionOpsResult;
    },
    retry: 1,
  });
}

export function useAeonInspiredOps(focusVar = 'scientific instrument sales') {
  return useQuery({
    queryKey: ['ai-operating-system-aeon-inspired-ops', focusVar],
    queryFn: async () => {
      const response = await httpClient.get('/api/ai-operating-system/aeon-inspired-ops', {
        params: { focus_var: focusVar },
      });
      return response.data?.data as AeonInspiredOpsResult;
    },
    retry: 1,
  });
}

export function useRunAeonInspiredHeartbeat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (focusVar = 'scientific instrument sales') => {
      const response = await httpClient.post('/api/ai-operating-system/aeon-inspired-ops/run-heartbeat', null, {
        params: { focus_var: focusVar },
      });
      return response.data?.data as AeonInspiredOpsResult & { persistence?: Record<string, unknown> };
    },
    onSuccess: (_data, focusVar) => {
      void queryClient.invalidateQueries({
        queryKey: ['ai-operating-system-aeon-inspired-ops', focusVar],
      });
      void queryClient.invalidateQueries({ queryKey: ['ai-operating-system-evolution-ops'] });
    },
  });
}

export function useDecideAgentProposal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      proposal_key: string;
      action: 'approve' | 'reject' | 'gray_release' | 'rollback';
      gray_percentage?: number;
      reviewer_note?: string;
    }) => {
      const response = await httpClient.post(
        `/api/ai-operating-system/proposals/${encodeURIComponent(payload.proposal_key)}/decision`,
        {
          action: payload.action,
          gray_percentage: payload.gray_percentage ?? 0,
          reviewer_note: payload.reviewer_note ?? '',
        },
      );
      return response.data?.data as {
        proposal_key: string;
        action: string;
        status: string;
        persistence: string;
      };
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['ai-operating-system-evolution-ops'] });
      void queryClient.invalidateQueries({ queryKey: ['ai-operating-system-improvement-proposals'] });
    },
  });
}
