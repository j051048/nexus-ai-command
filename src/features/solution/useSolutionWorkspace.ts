import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

import type {
  SolutionBrief,
  SolutionContextOptions,
  SolutionProject,
  SolutionVersionSummary,
  SolutionWorkspaceState,
} from './types';

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  message?: string;
}

const PROJECTS_KEY = ['solution-workspace', 'projects', 'v1'] as const;

export function useSolutionProjects() {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<{ projects: SolutionProject[] }>>(
        '/api/solution-workspace/projects',
        { silentError: true },
      );
      return response.data.data.projects;
    },
    staleTime: 30_000,
    retry: 1,
  });
}

export function useSolutionContextOptions() {
  return useQuery({
    queryKey: ['solution-workspace', 'context-options', 'v1'],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<SolutionContextOptions>>(
        '/api/solution-workspace/context-options',
        { silentError: true },
      );
      return response.data.data;
    },
    staleTime: 60_000,
    retry: 1,
  });
}

export function useSolutionVersions(projectId: string | null) {
  return useQuery({
    queryKey: ['solution-workspace', 'versions', projectId],
    queryFn: async () => {
      if (!projectId) return [];
      const response = await httpClient.get<ApiEnvelope<{ versions: SolutionVersionSummary[] }>>(
        `/api/solution-workspace/projects/${projectId}/versions`,
        { silentError: true },
      );
      return response.data.data.versions;
    },
    enabled: Boolean(projectId),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useCreateSolutionProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SolutionBrief) => {
      const response = await httpClient.post<ApiEnvelope<SolutionProject>>(
        '/api/solution-workspace/projects',
        input,
      );
      return response.data.data;
    },
    onSuccess: (project) => {
      queryClient.setQueryData<SolutionProject[]>(PROJECTS_KEY, (current = []) => [project, ...current]);
    },
  });
}

export function useSaveSolutionWorkspace(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (workspace: SolutionWorkspaceState) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.put<ApiEnvelope<SolutionProject>>(
        `/api/solution-workspace/projects/${projectId}/workspace`,
        workspace,
      );
      return response.data.data;
    },
    onSuccess: (project) => {
      queryClient.setQueryData<SolutionProject[]>(PROJECTS_KEY, (current = []) =>
        current.map((item) => (item.id === project.id ? project : item)),
      );
    },
  });
}

export function useGenerateSolution(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<{ project: SolutionProject; version: number; degraded: boolean }>>(
        `/api/solution-workspace/projects/${projectId}/generate`,
      );
      return response.data.data;
    },
    onSuccess: ({ project }) => {
      queryClient.setQueryData<SolutionProject[]>(PROJECTS_KEY, (current = []) =>
        current.map((item) => (item.id === project.id ? project : item)),
      );
      void queryClient.invalidateQueries({
        queryKey: ['solution-workspace', 'versions', project.id],
      });
    },
  });
}

export function useSolutionOutcome(projectId: string | null) {
  return useMutation({
    mutationFn: async (input: { outcome_type: 'proposal' | 'won' | 'lost' | 'revenue' | 'time_saved'; amount?: number; currency?: string; note?: string }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<Record<string, unknown>>>(
        `/api/solution-workspace/projects/${projectId}/outcome`,
        input,
      );
      return response.data.data;
    },
  });
}

export function usePromoteSolutionTemplate(projectId: string | null) {
  return useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<Record<string, unknown>>>(
        `/api/solution-workspace/projects/${projectId}/promote-template`,
      );
      return response.data.data;
    },
  });
}

export async function downloadSolution(projectId: string, format: 'markdown' | 'docx' | 'pdf') {
  const response = await httpClient.get(`/api/solution-workspace/projects/${projectId}/export`, {
    params: { format },
    responseType: 'blob',
    silentError: true,
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `solution-${projectId}.${format === 'markdown' ? 'md' : format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}
