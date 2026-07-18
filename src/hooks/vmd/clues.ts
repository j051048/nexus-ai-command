import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { aiClient } from '@/api/aiClient';
import type { BidProject, VMDClue, VMDFollowUp } from './types';

export interface ClueFilters {
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
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const query = params.toString();
      const response = await aiClient.fetch<{ success: boolean; data: VMDClue[] }>(
        `api/vmd/clues${query ? `?${query}` : ''}`
      );
      return response.data;
    },
    staleTime: 30_000,
  });
}

export function useCreateVMDClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<VMDClue>) => {
      const response = await aiClient.fetch<{ success: boolean; data: VMDClue }>('api/vmd/clues', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索创建成功');
    },
    onError: (error: Error) => toast.error(error.message || '创建线索失败'),
  });
}

export function useUpdateVMDClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<VMDClue> & { id: string }) => {
      const response = await aiClient.fetch<{ success: boolean; data: VMDClue }>(
        `api/vmd/clues/${data.id}`,
        { method: 'PATCH', body: JSON.stringify(data) }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索更新成功');
    },
    onError: (error: Error) => toast.error(error.message || '更新线索失败'),
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
    onError: (error: Error) => toast.error(error.message || '删除线索失败'),
  });
}

export function useBidProjects() {
  return useQuery({
    queryKey: ['vmd-bid-projects'],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: BidProject[];
      }>('api/vmd/bid-projects');
      return response.data;
    },
    staleTime: 60_000,
  });
}

export function useBidKeywords() {
  return useQuery({
    queryKey: ['vmd-bid-keywords'],
    queryFn: async () => {
      const response = await aiClient.fetch<{ success: boolean; data: string[] }>(
        'api/vmd/bid-keywords'
      );
      return response.data;
    },
  });
}

export function useUpdateBidKeywords() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (keywords: string[]) => {
      await aiClient.fetch('api/vmd/bid-keywords', {
        method: 'PUT',
        body: JSON.stringify({ keywords }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-bid-keywords'] });
      toast.success('关键词已更新');
    },
  });
}

export function useAddFollowUp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { clue_id: string; content: string }) => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: VMDFollowUp;
      }>(`api/vmd/clues/${data.clue_id}/follow-ups`, {
        method: 'POST',
        body: JSON.stringify({ content: data.content }),
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('跟进记录已添加');
    },
    onError: (error: Error) => toast.error(error.message || '添加跟进记录失败'),
  });
}

export function useConvertClue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (clueId: string) =>
      aiClient.fetch<{ success: boolean }>(`api/vmd/clues/${clueId}/convert`, {
        method: 'POST',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-clues'] });
      toast.success('线索已成功转化为客户');
    },
    onError: (error: Error) => toast.error(error.message || '转化失败'),
  });
}
