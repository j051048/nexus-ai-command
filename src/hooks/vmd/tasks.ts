import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { aiClient } from '@/api/aiClient';
import type { InstrumentLineCode } from '@/config/growthOperatingModel';
import { mapVMDTaskDetailFromAPI, mapVMDTaskListFromAPI } from '@/utils/vmdMapper';
import type { AnyData, VMDSubTask, VMDTask } from './types';

export interface TaskFilters {
  status?: string;
  priority?: string;
  scene_code?: string;
  date_from?: string;
  date_to?: string;
  instrument_line_code?: InstrumentLineCode;
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
      if (filters.instrument_line_code) {
        params.set('instrument_line_code', filters.instrument_line_code);
      }
      const query = params.toString();
      const response = await aiClient.fetch<{
        success: boolean;
        data: AnyData[] | { tasks: AnyData[] };
      }>(`api/vmd/tasks${query ? `?${query}` : ''}`);
      const rows = Array.isArray(response.data) ? response.data : response.data?.tasks || [];
      return mapVMDTaskListFromAPI(rows);
    },
    staleTime: 30_000,
  });
}

export function useVMDTaskDetail(taskId: string | null) {
  return useQuery({
    queryKey: ['vmd-task', taskId],
    queryFn: async () => {
      if (!taskId) return null;
      const response = await aiClient.fetch<{
        success: boolean;
        data: {
          task: AnyData;
          sub_tasks: VMDSubTask[];
          wbs_structure: AnyData | null;
          progress: {
            total_sub_tasks: number;
            completed: number;
            percentage: number;
          };
        };
      }>(`api/vmd/tasks/${taskId}`);
      return mapVMDTaskDetailFromAPI(response.data) as VMDTask;
    },
    enabled: Boolean(taskId),
  });
}

export function useCreateVMDTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      title: string;
      description: string;
      scene_code: string;
      priority: string;
      deadline?: string;
      instrument_line_code?: InstrumentLineCode;
      application_field?: string;
      target_product_models?: string[];
    }) => {
      const response = await aiClient.fetch<{ success: boolean; data: VMDTask }>('api/vmd/tasks', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-stats'] });
      toast.success('任务创建成功');
    },
    onError: (error: Error) => toast.error(error.message || '创建任务失败'),
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
    onError: (error: Error) => toast.error(error.message || '删除任务失败'),
  });
}

export function useAuditSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      subTaskId: string;
      action: 'approve' | 'reject';
      comment?: string;
    }) =>
      aiClient.fetch<{ success: boolean }>(`api/vmd/sub-tasks/${data.subTaskId}/audit`, {
        method: 'POST',
        body: JSON.stringify({ action: data.action, comment: data.comment }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('审核完成');
    },
    onError: (error: Error) => toast.error(error.message || '审核操作失败'),
  });
}

export function useSubmitSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { subTaskId: string; output: string }) =>
      aiClient.fetch<{ success: boolean }>(`api/vmd/sub-tasks/${data.subTaskId}/submit`, {
        method: 'POST',
        body: JSON.stringify({ output: data.output }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('任务输出已提交审核');
    },
    onError: (error: Error) => toast.error(error.message || '提交失败'),
  });
}

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
      const response = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/sub-tasks/${subTaskId}`,
        { method: 'PATCH', body: JSON.stringify(body) }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
    },
    onError: (error: Error) => toast.error(error.message || '更新子任务失败'),
  });
}

export function useCreateSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: {
      taskId: string;
      title: string;
      description?: string;
      agent_role?: string;
    }) => {
      const { taskId, ...body } = data;
      const response = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/tasks/${taskId}/sub-tasks`,
        { method: 'POST', body: JSON.stringify(body) }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('子任务已添加');
    },
    onError: (error: Error) => toast.error(error.message || '添加子任务失败'),
  });
}

export function useDeleteSubTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (subTaskId: string) => {
      const response = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/sub-tasks/${subTaskId}`,
        { method: 'DELETE' }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-task'] });
      queryClient.invalidateQueries({ queryKey: ['vmd-tasks'] });
      toast.success('子任务已删除');
    },
    onError: (error: Error) => toast.error(error.message || '删除子任务失败'),
  });
}
