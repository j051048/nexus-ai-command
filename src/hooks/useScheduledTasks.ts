import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';

// ─── Types ──────────────────────────────────────────────────

export interface ScheduledTask {
  id: string;
  user_id: string;
  organization_id?: string;
  name: string;
  prompt: string;
  schedule_type: 'daily' | 'weekly' | 'once' | 'interval';
  hour: number | null;
  minute: number;
  day_of_week: number | null;
  interval_minutes: number | null;
  is_active: boolean;
  notify_method: string;
  next_execution_at: string | null;
  last_executed_at: string | null;
  execution_count: number;
  created_at: string;
}

export interface CreateScheduledTaskInput {
  name: string;
  prompt: string;
  schedule_type: string;
  hour?: number | null;
  minute?: number;
  day_of_week?: number | null;
  interval_minutes?: number | null;
  notify_method?: string;
}

export interface UpdateScheduledTaskInput {
  name?: string;
  prompt?: string;
  schedule_type?: string;
  hour?: number | null;
  minute?: number;
  day_of_week?: number | null;
  interval_minutes?: number | null;
  is_active?: boolean;
  notify_method?: string;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

// ─── Constants ──────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// ─── Auth Fetch Helper ──────────────────────────────────────

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
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string>),
    },
  });

  if (!response.ok) {
    let errorMessage = `请求失败 (${response.status})`;
    try {
      const errorData = await response.json();
      if (errorData.error?.message) errorMessage = errorData.error.message;
      else if (typeof errorData.detail === 'string') errorMessage = errorData.detail;
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

// ─── Hooks ──────────────────────────────────────────────────

export function useScheduledTasks(includeInactive = false) {
  return useQuery({
    queryKey: ['scheduled-tasks', includeInactive],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (includeInactive) params.set('include_inactive', 'true');
      const result = await authFetch<ApiResponse<ScheduledTask[]>>(
        `api/scheduled-tasks?${params.toString()}`
      );
      return result.data ?? [];
    },
  });
}

export function useCreateScheduledTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateScheduledTaskInput) => {
      const result = await authFetch<ApiResponse<ScheduledTask>>(
        'api/scheduled-tasks',
        { method: 'POST', body: JSON.stringify(input) }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-tasks'] });
    },
  });
}

export function useUpdateScheduledTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, ...input }: UpdateScheduledTaskInput & { id: string }) => {
      const result = await authFetch<ApiResponse<ScheduledTask>>(
        `api/scheduled-tasks/${id}`,
        { method: 'PUT', body: JSON.stringify(input) }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-tasks'] });
    },
  });
}

export function useDeleteScheduledTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await authFetch<ApiResponse<null>>(
        `api/scheduled-tasks/${id}`,
        { method: 'DELETE' }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-tasks'] });
    },
  });
}

export function useRunScheduledTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const result = await authFetch<ApiResponse<{ task_id: string }>>(
        `api/scheduled-tasks/${id}/run`,
        { method: 'POST' }
      );
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-tasks'] });
    },
  });
}
