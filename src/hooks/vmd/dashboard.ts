import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { aiClient } from '@/api/aiClient';
import type {
  AnyData,
  ComplianceLog,
  ComplianceResult,
  ComplianceRule,
  VMDROIMetrics,
} from './types';

export function useVMDStats() {
  return useQuery({
    queryKey: ['vmd-stats'],
    queryFn: async () => {
      const response = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        'api/vmd/dashboard/stats'
      );
      return response.data;
    },
    staleTime: 30_000,
  });
}

export function useVMDROI() {
  return useQuery({
    queryKey: ['vmd-roi'],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: VMDROIMetrics;
      }>('api/vmd/dashboard/roi');
      return response.data;
    },
    staleTime: 60_000,
  });
}

export function useVMDDashboard(range: string = 'week') {
  return useQuery({
    queryKey: ['vmd-dashboard', range],
    queryFn: async () => {
      const response = await aiClient.fetch<{ success: boolean; data: AnyData }>(
        `api/vmd/dashboard?range=${range}`
      );
      return response.data;
    },
    staleTime: 60_000,
  });
}

export function useVMDTaskTrend(days: number = 30) {
  return useQuery({
    queryKey: ['vmd-task-trend', days],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: { trend: AnyData[]; days: number };
      }>(`api/vmd/dashboard/task-trend?days=${days}`);
      return (response.data?.trend || []).map((item: AnyData) => ({
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
      const response = await aiClient.fetch<{
        success: boolean;
        data: { distribution: AnyData[] };
      }>('api/vmd/dashboard/scene-distribution');
      return (response.data?.distribution || []).map((item: AnyData) => ({
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
      const response = await aiClient.fetch<{
        success: boolean;
        data: { workload: AnyData[] };
      }>('api/vmd/dashboard/agent-workload');
      return (response.data?.workload || []).map((item: AnyData) => ({
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
      const response = await aiClient.fetch<{
        success: boolean;
        data: { trend: AnyData[]; days: number };
      }>(`api/vmd/dashboard/compliance-trend?days=${days}`);
      return (response.data?.trend || []).map((item: AnyData) => ({
        ...item,
        clean: item.passed ?? 0,
      }));
    },
    staleTime: 60_000,
  });
}

export function useComplianceCheck() {
  return useMutation({
    mutationFn: async (data: { content: string; categories: string[] }) => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: ComplianceResult[];
      }>('api/vmd/compliance/check', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return response.data;
    },
  });
}

export function useComplianceRules() {
  return useQuery({
    queryKey: ['vmd-compliance-rules'],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: ComplianceRule[];
      }>('api/vmd/compliance/rules');
      return response.data;
    },
    staleTime: 60_000,
  });
}

export function useCreateComplianceRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<ComplianceRule>) => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: ComplianceRule;
      }>('api/vmd/compliance/rules', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-compliance-rules'] });
      toast.success('规则创建成功');
    },
    onError: (error: Error) => toast.error(error.message || '创建规则失败'),
  });
}

export function useDeleteComplianceRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ruleId: string) => {
      await aiClient.fetch(`api/vmd/compliance/rules/${ruleId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vmd-compliance-rules'] });
      toast.success('合规规则已删除');
    },
    onError: (error: Error) => toast.error(error.message || '删除合规规则失败'),
  });
}

export function useComplianceLogs() {
  return useQuery({
    queryKey: ['vmd-compliance-logs'],
    queryFn: async () => {
      const response = await aiClient.fetch<{
        success: boolean;
        data: ComplianceLog[];
      }>('api/vmd/compliance/history');
      return response.data;
    },
    staleTime: 30_000,
  });
}
