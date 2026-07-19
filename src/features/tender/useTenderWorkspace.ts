import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

import type { TenderProject, TenderProjectInput, TenderWorkspaceState } from './types';

interface ApiEnvelope<T> {
  success: boolean;
  data: T;
}

const PROJECTS_KEY = ['tender-workspace', 'projects', 'v1'] as const;

export function useTenderProjects() {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<{ projects: TenderProject[] }>>(
        '/api/tender-workspace/projects',
        { silentError: true },
      );
      return response.data.data.projects;
    },
    staleTime: 30_000,
    retry: 1,
  });
}

export function useCreateTenderProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: TenderProjectInput) => {
      const response = await httpClient.post<ApiEnvelope<TenderProject>>(
        '/api/tender-workspace/projects',
        input,
      );
      return response.data.data;
    },
    onSuccess: (project) => {
      queryClient.setQueryData<TenderProject[]>(PROJECTS_KEY, (current = []) => [project, ...current]);
    },
  });
}

export function useSaveTenderWorkspace(projectId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (workspace: TenderWorkspaceState) => {
      if (!projectId) throw new Error('请先创建或选择投标项目');
      const response = await httpClient.put<ApiEnvelope<TenderProject>>(
        `/api/tender-workspace/projects/${projectId}/workspace`,
        workspace,
      );
      return response.data.data;
    },
    onSuccess: (project) => {
      queryClient.setQueryData<TenderProject[]>(PROJECTS_KEY, (current = []) =>
        current.map((item) => (item.id === project.id ? project : item)),
      );
    },
  });
}
