import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// ---- Types ----

export interface WorkflowStep {
  id: string;
  type: 'initiator' | 'approver' | 'condition' | 'parallel' | 'auto_approve' | 'notify' | 'cc_notify' | 'timer' | 'sub_workflow' | 'end';
  label: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

export interface WorkflowCondition {
  from_step_id: string;
  to_step_id: string;
  label?: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface WorkflowDefinition {
  steps: WorkflowStep[];
  conditions: WorkflowCondition[];
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  approval_type: string;
  definition: WorkflowDefinition;
  is_active: boolean;
  is_default: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkflowPayload {
  name: string;
  description: string;
  approval_type: string;
  definition: WorkflowDefinition;
}

export interface UpdateWorkflowPayload extends CreateWorkflowPayload {
  id: string;
}

// ---- Auth Fetch Helper ----

async function authFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  let baseUrl = API_BASE_URL;
  if (!baseUrl.startsWith('http')) {
    baseUrl = baseUrl.includes('localhost') ? `http://${baseUrl}` : `https://${baseUrl}`;
  }
  const cleanBase = baseUrl.replace(/\/$/, '');
  const cleanEndpoint = url.startsWith('/') ? url.slice(1) : url;
  const fullUrl = `${cleanBase}/${cleanEndpoint}`;

  const response = await fetch(fullUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string>),
    },
  });

  if (!response.ok) {
    let errorMessage = `请求失败 (${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData.error?.message) {
        errorMessage = errorData.error.message;
      } else if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string'
          ? errorData.detail
          : Array.isArray(errorData.detail)
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ? errorData.detail.map((d: any) => d.msg).join(', ')
            : errorMessage;
      }
    } catch {
      // ignore json parse errors
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// ---- Hooks ----

export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const result = await authFetch<{ data: Workflow[] }>('api/workflows');
      return Array.isArray(result.data) ? result.data : [];
    },
  });
}

export function useWorkflow(id: string | undefined) {
  return useQuery({
    queryKey: ['workflows', id],
    queryFn: async () => {
      if (!id) return null;
      const result = await authFetch<{ data: Workflow }>(`api/workflows/${id}`);
      return result.data ?? null;
    },
    enabled: !!id && id !== 'new',
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateWorkflowPayload) => {
      const result = await authFetch<{ data: Workflow }>('api/workflows', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: UpdateWorkflowPayload) => {
      const { id, ...rest } = payload;
      const result = await authFetch<{ data: Workflow }>(`api/workflows/${id}`, {
        method: 'PUT',
        body: JSON.stringify(rest),
      });
      return result.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      queryClient.invalidateQueries({ queryKey: ['workflows', variables.id] });
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await authFetch<{ success: boolean }>(`api/workflows/${id}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}

export function useToggleWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const result = await authFetch<{ data: Workflow }>(`api/workflows/${id}/toggle`, {
        method: 'POST',
      });
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}

export function useSetDefaultWorkflow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const result = await authFetch<{ data: Workflow }>(`api/workflows/${id}/set-default`, {
        method: 'POST',
      });
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}

export function useApprovalTypes() {
  return useQuery({
    queryKey: ['workflow-types'],
    queryFn: async () => {
      const result = await authFetch<{ data: string[] }>('api/workflows/types');
      return result.data ?? [];
    },
  });
}
