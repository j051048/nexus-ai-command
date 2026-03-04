/**
 * VMD (虚拟市场部) API Hooks
 * 使用 @tanstack/react-query + aiClient 统一模式
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';
import { mapVMDTaskListFromAPI, mapVMDTaskDetailFromAPI } from '@/utils/vmdMapper';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

// ─── Types ───────────────────────────────────────────────────

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
  model_tier: 'high' | 'standard';
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

// ─── VMD Tasks ───────────────────────────────────────────────

interface TaskFilters {
  status?: string;
  priority?: string;
  scene_code?: string;
  date_from?: string;
  date_to?: string;
}

export function useVMDTasks(filters: TaskFilters = {}) {
  return useQuery({
    queryKey: ['vmd-tasks', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set('status', filters.status);
      if (filters.priority) params.set('priority', filters.priority);
      if (filters.scene_code) params.set('scene_code', filters.scene_code);
      if (filters.date_from) params.set('date_from', filters.date_from);
      if (filters.date_to) params.set('date_to', filters.date_to);
      const qs = params.toString();
      const res = await aiClient.fetch<{ success: boolean; data: AnyData[] }>(
        `api/vmd/tasks${qs ? '?' + qs : ''}`
      );
      // Use centralized VMD mapper for consistent field normalization
      return mapVMDTaskListFromAPI(res.data || []);
    },
    staleTime: 30_000,
  });
}

export function useVMDTaskDetail(taskId: string | null) {
  return useQuery({
    queryKey: ['vmd-task', taskId],
    queryFn: async () => {
      if (!taskId) return null;
      // Backend returns { task, sub_tasks, wbs_structure, progress: {total_sub_tasks, completed, percentage} }
      const res = await aiClient.fetch<{ success: boolean; data: {
        task: AnyData;
        sub_tasks: VMDSubTask[];
        wbs_structure: AnyData | null;
        progress: { total_sub_tasks: number; completed: number; percentage: number };
      } }>(
        `api/vmd/tasks/${taskId}`
      );
      // Use centralized VMD mapper for consistent field normalization
      return mapVMDTaskDetailFromAPI(res.data) as VMDTask;
    },
    enabled: !!taskId,
  });
}

export function useCreateVMDTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { title: string; description: string; scene_code: string; priority: string; deadline?: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: VMDTask }>(
        'api/vmd/tasks', { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-stats'] });
      toast.success('任务创建成功');
    },
    onError: (err: Error) => toast.error(err.message || '创建任务失败'),
  });
}

export function useDeleteVMDTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => {
      await aiClient.fetch(`api/vmd/tasks/${taskId}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-stats'] });
      toast.success('任务已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除任务失败'),
  });
}

export function useAuditSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { subTaskId: string; action: 'approve' | 'reject'; comment?: string }) => {
      const res = await aiClient.fetch<{ success: boolean }>(
        `api/vmd/sub-tasks/${data.subTaskId}/audit`,
        { method: 'POST', body: JSON.stringify({ action: data.action, comment: data.comment }) }
      );
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('审核完成');
    },
    onError: (err: Error) => toast.error(err.message || '审核操作失败'),
  });
}

export function useSubmitSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { subTaskId: string; output: string }) => {
      const res = await aiClient.fetch<{ success: boolean }>(
        `api/vmd/sub-tasks/${data.subTaskId}/submit`,
        { method: 'POST', body: JSON.stringify({ output: data.output }) }
      );
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('任务输出已提交审核');
    },
    onError: (err: Error) => toast.error(err.message || '提交失败'),
  });
}

// ─── Sub-task Human-centric CRUD ─────────────────────────────

export interface UpdateSubTaskPayload {
  title?: string;
  description?: string;
  progress?: number;
  status?: 'todo' | 'in_progress' | 'done';
  human_notes?: string;
  assignee_id?: string;
  assignee_name?: string;
  weight?: number;
  sort_order?: number;
  start_date?: string | null;
  due_date?: string | null;
}

export function useUpdateSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { subTaskId: string } & UpdateSubTaskPayload) => {
      const { subTaskId, ...body } = data;
      const res = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/sub-tasks/${subTaskId}`,
        { method: 'PATCH', body: JSON.stringify(body) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
    },
    onError: (err: Error) => toast.error(err.message || '更新子任务失败'),
  });
}

export function useCreateSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { taskId: string; title: string; description?: string; agent_role?: string }) => {
      const { taskId, ...body } = data;
      const res = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/tasks/${taskId}/sub-tasks`,
        { method: 'POST', body: JSON.stringify(body) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('子任务已添加');
    },
    onError: (err: Error) => toast.error(err.message || '添加子任务失败'),
  });
}

export function useDeleteSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (subTaskId: string) => {
      const res = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/sub-tasks/${subTaskId}`,
        { method: 'DELETE' }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('子任务已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除子任务失败'),
  });
}

// ─── VMD Agents ──────────────────────────────────────────────

/** Map DB row field names to frontend VMDAgent field names */
function mapAgentFromDB(row: AnyData): VMDAgent {
  return {
    id: String(row.id),
    agent_code: row.agent_code ?? '',
    name: row.agent_name ?? row.name ?? '',
    role_description: row.agent_role ?? row.role_description ?? '',
    system_prompt: row.system_prompt ?? '',
    tool_whitelist: row.tool_whitelist ?? [],
    scene_codes: row.scene_codes ?? [],
    model_tier: row.recommended_model_tier === 'high' ? 'high' : 'standard',
    is_active: row.is_active ?? true,
    icon: row.icon ?? '',
  };
}

export function useVMDAgents() {
  return useQuery({
    queryKey: ['vmd-agents'],
    queryFn: async () => {
      try {
        const res = await aiClient.fetch<{ success: boolean; data: { agents: AnyData[] } }>('api/vmd/agents/config');
        const rows = res.data?.agents ?? (Array.isArray(res.data) ? res.data : []);
        return rows.map(mapAgentFromDB);
      } catch {
        // API unreachable or auth error — return empty so page falls back to defaults
        return [] as VMDAgent[];
      }
    },
    staleTime: 60_000,
    retry: 1,
  });
}

export function useUpdateVMDAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<VMDAgent> & { id: string; agent_code?: string }) => {
      const agentCode = data.agent_code;
      if (!agentCode) throw new Error('缺少 agent_code');
      // Map frontend fields to backend DB column names
      const payload: AnyData = {};
      if (data.system_prompt !== undefined) payload.system_prompt = data.system_prompt;
      if (data.tool_whitelist !== undefined) payload.tool_whitelist = data.tool_whitelist;
      if (data.scene_codes !== undefined) payload.scene_codes = data.scene_codes;
      if (data.is_active !== undefined) payload.is_active = data.is_active;
      if (data.model_tier !== undefined) payload.recommended_model_tier = data.model_tier;
      const res = await aiClient.fetch<{ success: boolean; data: { agent: AnyData } }>(
        `api/vmd/agents/config/${agentCode}`,
        { method: 'PUT', body: JSON.stringify(payload) }
      );
      const row = res.data?.agent ?? res.data;
      if (!row || typeof row !== 'object' || !row.id) {
        throw new Error('服务端返回数据异常，请重试');
      }
      return mapAgentFromDB(row);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-agents'] });
      toast.success('Agent 配置已更新');
    },
    onError: (err: Error) => toast.error(err.message || '更新 Agent 失败'),
  });
}

// ─── LLM Models ──────────────────────────────────────────────

/** Map DB row field names to frontend LLMModel field names */
function mapModelFromDB(row: AnyData): LLMModel {
  return {
    id: String(row.id),
    provider_type: row.provider_type ?? row.adapter_code ?? '',
    model_code: row.model_code ?? '',
    model_name: row.model_name ?? '',
    api_base_url: row.api_base_url ?? '',
    api_key: row.api_key,
    secret_key: row.secret_key,
    model_id: row.model_id ?? '',
    model_type: row.model_type ?? 'chat',
    timeout_ms: row.timeout_ms ?? 30000,
    max_tokens: row.max_tokens ?? 4096,
    context_window: row.context_window ?? 8192,
    supports_tools: row.supports_tools ?? false,
    supports_streaming: row.supports_streaming ?? true,
    input_price: row.input_price_per_1m != null ? row.input_price_per_1m / 1000 : (row.input_price ?? 0),
    output_price: row.output_price_per_1m != null ? row.output_price_per_1m / 1000 : (row.output_price ?? 0),
    is_active: row.status === 'enabled' || row.status === 'active' || row.is_active === true,
    is_default: row.is_default ?? false,
  };
}

export function useLLMModels() {
  return useQuery({
    queryKey: ['llm-models'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: AnyData[] }>('api/llm/models');
      const rows = Array.isArray(res.data) ? res.data : [];
      return rows.map(mapModelFromDB);
    },
    staleTime: 60_000,
  });
}

export function useCreateLLMModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<LLMModel>) => {
      const res = await aiClient.fetch<{ success: boolean; data: LLMModel }>(
        'api/llm/models', { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      toast.success('模型添加成功');
    },
    onError: (err: Error) => toast.error(err.message || '添加模型失败'),
  });
}

export function useUpdateLLMModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<LLMModel> & { id: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: LLMModel }>(
        `api/llm/models/${data.id}`,
        { method: 'PUT', body: JSON.stringify(data) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      toast.success('模型更新成功');
    },
    onError: (err: Error) => toast.error(err.message || '更新模型失败'),
  });
}

export function useDeleteLLMModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await aiClient.fetch(`api/llm/models/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      toast.success('模型已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除模型失败'),
  });
}

export function useTestLLMModel() {
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await aiClient.fetch<{ success: boolean; latency_ms: number }>(
        `api/llm/models/${id}/test`, { method: 'POST' }
      );
      return res;
    },
  });
}

export function useScheduleRules() {
  return useQuery({
    queryKey: ['llm-schedule-rules'],
    queryFn: async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const res = await aiClient.fetch<{ success: boolean; data: any[] }>('api/llm/schedule-rules');
      const rows = Array.isArray(res.data) ? res.data : [];
      return rows.map((r): ScheduleRule => ({
        id: String(r.id),
        rule_name: r.rule_name ?? '',
        scene_code: r.scene_code ?? '',
        agent_code: r.agent_code ?? '',
        primary_model: String(r.primary_model_id ?? r.primary_model_code ?? ''),
        backup_model: String(r.backup_model_id ?? r.backup_model_code ?? ''),
        strategy: r.load_balance_strategy ?? 'priority',
        complexity_tier: r.complexity_tier ?? null,
        priority: r.priority ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

export function useCreateScheduleRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      rule_name: string;
      scene_code: string;
      agent_code?: string;
      primary_model_id: string;
      backup_model_id?: string;
      load_balance_strategy?: string;
      priority?: number;
      complexity_tier?: string;
    }) => {
      const res = await aiClient.fetch<{ success: boolean; data: { rule: ScheduleRule } }>(
        'api/llm/schedule-rules',
        { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data?.rule;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-schedule-rules'] });
      toast.success('调度规则创建成功');
    },
    onError: (err: Error) => toast.error(err.message || '创建调度规则失败'),
  });
}

export function useUpdateScheduleRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { id: string } & Record<string, unknown>) => {
      const { id, ...body } = data;
      const res = await aiClient.fetch<{ success: boolean; data: { rule: ScheduleRule } }>(
        `api/llm/schedule-rules/${id}`,
        { method: 'PUT', body: JSON.stringify(body) }
      );
      return res.data?.rule;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-schedule-rules'] });
      toast.success('调度规则已更新');
    },
    onError: (err: Error) => toast.error(err.message || '更新调度规则失败'),
  });
}

export function useDeleteScheduleRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await aiClient.fetch(`api/llm/schedule-rules/${id}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-schedule-rules'] });
      toast.success('调度规则已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除调度规则失败'),
  });
}

export function useModelUsageStats(range: string = 'week') {
  return useQuery({
    queryKey: ['llm-usage-stats', range],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { usage: AnyData[] } }>(
        'api/vmd/dashboard/model-usage'
      );
      return (res.data?.usage || []).map((item: AnyData) => ({
        ...item,
        model_code: item.model_code ?? 'unknown',
        total_tokens: (item.total_input_tokens ?? 0) + (item.total_output_tokens ?? 0),
        call_count: item.call_count ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

// ─── Model Marketplace (可用模型市场) ─────────────────────────

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

export function useFetchAvailableModels(filters?: { search?: string; type?: string; tag?: string }) {
  return useQuery({
    queryKey: ['llm-available-models', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.search) params.set('search', filters.search);
      if (filters?.type) params.set('type', filters.type);
      if (filters?.tag) params.set('tag', filters.tag);
      const qs = params.toString();
      const res = await aiClient.fetch<{ success: boolean; data: AvailableModelsResponse }>(
        `api/llm/available-models${qs ? '?' + qs : ''}`
      );
      return res.data;
    },
    staleTime: 300_000, // 5min — available models don't change often
    retry: 1,
  });
}

export function useQuickAddModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (model: AvailableModel) => {
      // Build the payload with pre-filled metadata from the catalog
      const payload = {
        model_code: model.model_id,
        model_name: model.name,
        provider_type: 'openai',  // All go through OpenAI-compatible relay
        adapter_code: 'openai',
        api_base_url: '',  // Will use system default
        api_key: '__SYSTEM_DEFAULT__',  // Backend will recognize this sentinel
        model_id: model.model_id,
        model_type: model.type,
        timeout_ms: 30000,
        max_tokens: model.max_tokens || 4096,
        context_window: model.context_window || 8192,
        supports_tools: model.supports_tools,
        supports_streaming: model.supports_streaming,
        input_price_per_1m: model.input_price_per_1m,
        output_price_per_1m: model.output_price_per_1m,
        status: 'enabled',
      };
      const res = await aiClient.fetch<{ success: boolean; data: LLMModel }>(
        'api/llm/models', { method: 'POST', body: JSON.stringify(payload) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      queryClient.invalidateQueries({ queryKey: ['llm-available-models'] });
      toast.success('模型添加成功');
    },
    onError: (err: Error) => toast.error(err.message || '添加模型失败'),
  });
}

// ─── VMD Clues ───────────────────────────────────────────────

interface ClueFilters {
  status?: string;
  level?: string;
  source?: string;
  assigned_to?: string;
  search?: string;
}

export function useVMDClues(filters: ClueFilters = {}) {
  return useQuery({
    queryKey: ['vmd-clues', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
      const qs = params.toString();
      const res = await aiClient.fetch<{ success: boolean; data: VMDClue[] }>(
        `api/vmd/clues${qs ? '?' + qs : ''}`
      );
      return res.data;
    },
    staleTime: 30_000,
  });
}

export function useCreateVMDClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<VMDClue>) => {
      const res = await aiClient.fetch<{ success: boolean; data: VMDClue }>(
        'api/vmd/clues', { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索创建成功');
    },
    onError: (err: Error) => toast.error(err.message || '创建线索失败'),
  });
}

export function useUpdateVMDClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<VMDClue> & { id: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: VMDClue }>(
        `api/vmd/clues/${data.id}`,
        { method: 'PATCH', body: JSON.stringify(data) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索更新成功');
    },
    onError: (err: Error) => toast.error(err.message || '更新线索失败'),
  });
}

export function useDeleteVMDClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (clueId: string) => {
      await aiClient.fetch(`api/vmd/clues/${clueId}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除线索失败'),
  });
}

export function useBidProjects() {
  return useQuery({
    queryKey: ['vmd-bid-projects'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: BidProject[] }>('api/vmd/bid-projects');
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function useBidKeywords() {
  return useQuery({
    queryKey: ['vmd-bid-keywords'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: string[] }>('api/vmd/bid-keywords');
      return res.data;
    },
  });
}

export function useUpdateBidKeywords() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (keywords: string[]) => {
      await aiClient.fetch('api/vmd/bid-keywords', { method: 'PUT', body: JSON.stringify({ keywords }) });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-bid-keywords'] });
      toast.success('关键词已更新');
    },
  });
}

// ─── VMD Dashboard / Stats ───────────────────────────────────

export function useVMDStats() {
  return useQuery({
    queryKey: ['vmd-stats'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: AnyData }>('api/vmd/dashboard/stats');
      return res.data;
    },
    staleTime: 30_000,
  });
}

export function useVMDDashboard(range: string = 'week') {
  return useQuery({
    queryKey: ['vmd-dashboard', range],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/dashboard?range=${range}`
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}

// ─── VMD Dashboard Charts ────────────────────────────────────

export function useVMDTaskTrend(days: number = 30) {
  return useQuery({
    queryKey: ['vmd-task-trend', days],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { trend: AnyData[]; days: number } }>(
        `api/vmd/dashboard/task-trend?days=${days}`
      );
      return (res.data?.trend || []).map((item: AnyData) => ({
        ...item,
        created: item.total ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

export function useVMDSceneDistribution() {
  return useQuery({
    queryKey: ['vmd-scene-distribution'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { distribution: AnyData[] } }>(
        'api/vmd/dashboard/scene-distribution'
      );
      return (res.data?.distribution || []).map((item: AnyData) => ({
        ...item,
        count: item.total ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

export function useVMDAgentWorkload() {
  return useQuery({
    queryKey: ['vmd-agent-workload'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { workload: AnyData[] } }>(
        'api/vmd/dashboard/agent-workload'
      );
      return (res.data?.workload || []).map((item: AnyData) => ({
        ...item,
        agent_name: item.agent_code ?? 'unknown',
        executing: item.running ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

export function useVMDComplianceTrend(days: number = 30) {
  return useQuery({
    queryKey: ['vmd-compliance-trend', days],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: { trend: AnyData[]; days: number } }>(
        `api/vmd/dashboard/compliance-trend?days=${days}`
      );
      return (res.data?.trend || []).map((item: AnyData) => ({
        ...item,
        clean: item.passed ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

// ─── VMD Clue Follow-ups & Conversion ────────────────────────

export function useAddFollowUp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { clue_id: string; content: string }) => {
      const res = await aiClient.fetch<{ success: boolean; data: VMDFollowUp }>(
        `api/vmd/clues/${data.clue_id}/follow-ups`,
        { method: 'POST', body: JSON.stringify({ content: data.content }) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('跟进记录已添加');
    },
    onError: (err: Error) => toast.error(err.message || '添加跟进记录失败'),
  });
}

export function useConvertClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (clueId: string) => {
      const res = await aiClient.fetch<{ success: boolean }>(
        `api/vmd/clues/${clueId}/convert`,
        { method: 'POST' }
      );
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索已成功转化为客户');
    },
    onError: (err: Error) => toast.error(err.message || '转化失败'),
  });
}

// ─── Compliance ──────────────────────────────────────────────

export function useComplianceCheck() {
  return useMutation({
    mutationFn: async (data: { content: string; categories: string[] }) => {
      const res = await aiClient.fetch<{ success: boolean; data: ComplianceResult[] }>(
        'api/vmd/compliance/check', { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data;
    },
  });
}

export function useComplianceRules() {
  return useQuery({
    queryKey: ['vmd-compliance-rules'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: ComplianceRule[] }>('api/vmd/compliance/rules');
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function useCreateComplianceRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<ComplianceRule>) => {
      const res = await aiClient.fetch<{ success: boolean; data: ComplianceRule }>(
        'api/vmd/compliance/rules', { method: 'POST', body: JSON.stringify(data) }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-compliance-rules'] });
      toast.success('规则创建成功');
    },
    onError: (err: Error) => toast.error(err.message || '创建规则失败'),
  });
}

export function useDeleteComplianceRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ruleId: string) => {
      await aiClient.fetch(`api/vmd/compliance/rules/${ruleId}`, { method: 'DELETE' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-compliance-rules'] });
      toast.success('合规规则已删除');
    },
    onError: (err: Error) => toast.error(err.message || '删除合规规则失败'),
  });
}

export function useComplianceLogs() {
  return useQuery({
    queryKey: ['vmd-compliance-logs'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: ComplianceLog[] }>('api/vmd/compliance/history');
      return res.data;
    },
    staleTime: 30_000,
  });
}
