import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { aiClient } from '@/api/aiClient';
import type {
  AnyData,
  AvailableModel,
  AvailableModelsResponse,
  LLMModel,
  ScheduleRule,
  VMDAgent,
} from './types';

function mapAgentFromDB(row: AnyData): VMDAgent {
  return {
    id: String(row.id),
    agent_code: row.agent_code ?? '',
    name: row.agent_name ?? row.name ?? '',
    role_description: row.agent_role ?? row.role_description ?? '',
    system_prompt: row.system_prompt ?? '',
    tool_whitelist: row.tool_whitelist ?? [],
    scene_codes: row.scene_codes ?? [],
    model_tier: row.recommended_model_tier ?? 'standard',
    is_active: row.is_active ?? true,
    icon: row.icon ?? '',
  };
}

export function useVMDAgents() {
  return useQuery({
    queryKey: ['vmd-agents'],
    queryFn: async () => {
      try {
        const response = await aiClient.fetch<{
          success: boolean;
          data: { agents: AnyData[] };
        }>('api/vmd/agents/config');
        const rows = response.data?.agents ?? (Array.isArray(response.data) ? response.data : []);
        return rows.map(mapAgentFromDB);
      } catch {
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

      const payload: AnyData = {};
      if (data.system_prompt !== undefined) payload.system_prompt = data.system_prompt;
      if (data.tool_whitelist !== undefined) payload.tool_whitelist = data.tool_whitelist;
      if (data.scene_codes !== undefined) payload.scene_codes = data.scene_codes;
      if (data.is_active !== undefined) payload.is_active = data.is_active;
      if (data.model_tier !== undefined) {
        payload.recommended_model_tier = data.model_tier;
      }

      const response = await aiClient.fetch<{
        success: boolean;
        data: { agent: AnyData };
      }>(`api/vmd/agents/config/${agentCode}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      const row = (
        response.data && 'agent' in response.data ? response.data.agent : response.data
      ) as AnyData;
      if (!row || typeof row !== 'object' || !('id' in row)) {
        throw new Error('服务端返回数据异常，请重试');
      }
      return mapAgentFromDB(row);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-agents'] });
      toast.success('Agent 配置已更新');
    },
    onError: (error: Error) => toast.error(error.message || '更新 Agent 失败'),
  });
}

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
    timeout_ms: row.timeout_ms ?? 30_000,
    max_tokens: row.max_tokens ?? 4096,
    context_window: row.context_window ?? 8192,
    supports_tools: row.supports_tools ?? false,
    supports_streaming: row.supports_streaming ?? true,
    input_price:
      row.input_price_per_1m != null ? row.input_price_per_1m / 1000 : (row.input_price ?? 0),
    output_price:
      row.output_price_per_1m != null ? row.output_price_per_1m / 1000 : (row.output_price ?? 0),
    is_active: row.status === 'enabled' || row.status === 'active' || row.is_active === true,
    is_default: row.is_default ?? false,
  };
}

export function useLLMModels() {
  return useQuery({
    queryKey: ['llm-models'],
    queryFn: async () => {
      const response = await aiClient.fetch<{ success: boolean; data: AnyData[] }>(
        'api/llm/models'
      );
      const rows = Array.isArray(response.data) ? response.data : [];
      return rows.map(mapModelFromDB);
    },
    staleTime: 60_000,
  });
}

export function useCreateLLMModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<LLMModel>) => {
      const response = await aiClient.fetch<{ success: boolean; data: LLMModel }>(
        'api/llm/models',
        { method: 'POST', body: JSON.stringify(data) }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      toast.success('模型添加成功');
    },
    onError: (error: Error) => toast.error(error.message || '添加模型失败'),
  });
}

export function useUpdateLLMModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<LLMModel> & { id: string }) => {
      const response = await aiClient.fetch<{ success: boolean; data: LLMModel }>(
        `api/llm/models/${data.id}`,
        { method: 'PUT', body: JSON.stringify(data) }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      toast.success('模型更新成功');
    },
    onError: (error: Error) => toast.error(error.message || '更新模型失败'),
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
    onError: (error: Error) => toast.error(error.message || '删除模型失败'),
  });
}

export function useTestLLMModel() {
  return useMutation({
    mutationFn: async (id: string) =>
      aiClient.fetch<{ success: boolean; latency_ms: number }>(`api/llm/models/${id}/test`, {
        method: 'POST',
      }),
  });
}

export function useScheduleRules() {
  return useQuery({
    queryKey: ['llm-schedule-rules'],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: Record<string, unknown>[];
      }>('api/llm/schedule-rules');
      const rows = Array.isArray(response.data) ? response.data : [];
      return rows.map((row): ScheduleRule => ({
        id: String(row.id),
        rule_name: String(row.rule_name ?? ''),
        scene_code: String(row.scene_code ?? ''),
        agent_code: String(row.agent_code ?? ''),
        primary_model: String(row.primary_model_id ?? row.primary_model_code ?? ''),
        backup_model: String(row.backup_model_id ?? row.backup_model_code ?? ''),
        strategy: String(row.load_balance_strategy ?? 'priority'),
        complexity_tier: row.complexity_tier == null ? null : String(row.complexity_tier),
        priority: Number(row.priority ?? 0),
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
      const response = await aiClient.fetch<{
        success: boolean;
        data: { rule: ScheduleRule };
      }>('api/llm/schedule-rules', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return response.data?.rule;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-schedule-rules'] });
      toast.success('调度规则创建成功');
    },
    onError: (error: Error) => toast.error(error.message || '创建调度规则失败'),
  });
}

export function useUpdateScheduleRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { id: string } & Record<string, unknown>) => {
      const { id, ...body } = data;
      const response = await aiClient.fetch<{
        success: boolean;
        data: { rule: ScheduleRule };
      }>(`api/llm/schedule-rules/${id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      return response.data?.rule;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-schedule-rules'] });
      toast.success('调度规则已更新');
    },
    onError: (error: Error) => toast.error(error.message || '更新调度规则失败'),
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
    onError: (error: Error) => toast.error(error.message || '删除调度规则失败'),
  });
}

export function useModelUsageStats(range: string = 'week') {
  const days = range === 'month' ? 30 : 7;
  return useQuery({
    queryKey: ['llm-usage-stats', range],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: { history: AnyData[] };
      }>(`api/usage/history?days=${days}`);
      return response.data?.history || [];
    },
    staleTime: 60_000,
  });
}

export function useFetchAvailableModels(filters?: {
  search?: string;
  type?: string;
  tag?: string;
}) {
  return useQuery({
    queryKey: ['llm-available-models', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.search) params.set('search', filters.search);
      if (filters?.type) params.set('type', filters.type);
      if (filters?.tag) params.set('tag', filters.tag);
      const query = params.toString();
      const response = await aiClient.fetch<{
        success: boolean;
        data: AvailableModelsResponse;
      }>(`api/llm/available-models${query ? `?${query}` : ''}`);
      return response.data;
    },
    staleTime: 300_000,
    retry: 1,
  });
}

export function useQuickAddModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (model: AvailableModel) => {
      const payload = {
        model_code: model.model_id,
        model_name: model.name,
        provider_type: 'openai',
        adapter_code: 'openai',
        api_base_url: '',
        api_key: '__SYSTEM_DEFAULT__',
        model_id: model.model_id,
        model_type: model.type,
        timeout_ms: 30_000,
        max_tokens: model.max_tokens || 4096,
        context_window: model.context_window || 8192,
        supports_tools: model.supports_tools,
        supports_streaming: model.supports_streaming,
        input_price_per_1m: model.input_price_per_1m,
        output_price_per_1m: model.output_price_per_1m,
        status: 'enabled',
      };
      const response = await aiClient.fetch<{
        success: boolean;
        data: LLMModel;
      }>('api/llm/models', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-models'] });
      queryClient.invalidateQueries({ queryKey: ['llm-available-models'] });
      toast.success('模型添加成功');
    },
    onError: (error: Error) => toast.error(error.message || '添加模型失败'),
  });
}
