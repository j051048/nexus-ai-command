import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

import type {
  SolutionBrief,
  SolutionAnalytics,
  SolutionCPQPreview,
  SolutionCommercialApproval,
  SolutionConnector,
  SolutionContextOptions,
  SolutionDeliveryEvent,
  SolutionEvaluation,
  SolutionProductOption,
  SolutionProject,
  SolutionReviewComment,
  TenderReadiness,
  SolutionVersionSummary,
  SolutionVersionDetail,
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

export function useSolutionAnalytics() {
  return useQuery({
    queryKey: ['solution-workspace', 'analytics', 'v1'],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<SolutionAnalytics>>(
        '/api/solution-workspace/analytics',
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
    mutationFn: async (input?: { force?: boolean }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<{ project: SolutionProject; version: number; degraded: boolean; cached?: boolean }>>(
        `/api/solution-workspace/projects/${projectId}/generate`,
        undefined,
        { params: { force: input?.force || false } },
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

export function useSolutionCPQ(projectId: string | null) {
  return useMutation({
    mutationFn: async (input: { workspace: SolutionWorkspaceState; price_book_id?: string; tax_rate?: number }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<SolutionCPQPreview>>(
        `/api/solution-workspace/projects/${projectId}/cpq-preview`,
        input,
      );
      return response.data.data;
    },
  });
}

export function useCommercialApprovals(projectId: string | null) {
  return useQuery({
    queryKey: ['solution-workspace', 'commercial-approvals', projectId],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<{ approvals: SolutionCommercialApproval[] }>>(
        `/api/solution-workspace/projects/${projectId}/commercial-approvals`,
        { silentError: true },
      );
      return response.data.data.approvals;
    },
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useRequestCommercialApproval(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      package_id: string;
      workspace: SolutionWorkspaceState;
      price_book_id?: string;
      tax_rate?: number;
      reason: string;
    }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<SolutionCommercialApproval>>(
        `/api/solution-workspace/projects/${projectId}/commercial-approvals`,
        input,
      );
      return response.data.data;
    },
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: ['solution-workspace', 'commercial-approvals', projectId],
    }),
  });
}

export function useSolutionEvaluation(projectId: string | null) {
  return useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<SolutionEvaluation>>(
        `/api/solution-workspace/projects/${projectId}/evaluate`,
      );
      return response.data.data;
    },
  });
}

export function useTenderReadiness(projectId: string | null) {
  return useQuery({
    queryKey: ['solution-workspace', 'tender-readiness', projectId],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<TenderReadiness>>(
        `/api/solution-workspace/projects/${projectId}/tender-readiness`,
        { silentError: true },
      );
      return response.data.data;
    },
    enabled: Boolean(projectId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useSolutionConnectors(enabled = true) {
  return useQuery({
    queryKey: ['solution-workspace', 'connectors', 'v1'],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<{ connectors: SolutionConnector[] }>>(
        '/api/solution-workspace/connectors',
        { silentError: true },
      );
      return response.data.data.connectors;
    },
    enabled,
    staleTime: 60_000,
    retry: false,
  });
}

export function useDeliverSolution(projectId: string | null) {
  return useMutation({
    mutationFn: async (input: { connector_code: string; request_key: string }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<SolutionDeliveryEvent>>(
        `/api/solution-workspace/projects/${projectId}/deliver`,
        input,
      );
      return response.data.data;
    },
  });
}

export function useSolutionComments(projectId: string | null) {
  return useQuery({
    queryKey: ['solution-workspace', 'comments', projectId],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<{ comments: SolutionReviewComment[] }>>(
        `/api/solution-workspace/projects/${projectId}/comments`,
        { silentError: true },
      );
      return response.data.data.comments;
    },
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useSolutionVersionDetail(projectId: string | null, versionNumber: number | null) {
  return useQuery({
    queryKey: ['solution-workspace', 'version-detail', projectId, versionNumber],
    queryFn: async () => {
      const response = await httpClient.get<ApiEnvelope<SolutionVersionDetail>>(
        `/api/solution-workspace/projects/${projectId}/versions/${versionNumber}`,
        { silentError: true },
      );
      return response.data.data;
    },
    enabled: Boolean(projectId && versionNumber),
    retry: false,
  });
}

export function useCreateSolutionComment(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { section_id: string; content: string }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<SolutionReviewComment>>(
        `/api/solution-workspace/projects/${projectId}/comments`,
        input,
      );
      return response.data.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['solution-workspace', 'comments', projectId] }),
  });
}

export function useRewriteSolutionSection(projectId: string | null) {
  return useMutation({
    mutationFn: async (input: { section_id: string; mode: 'concise' | 'technical' | 'executive' | 'proofread'; instruction?: string }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<{
        section_id: string;
        original_content: string;
        revised_content: string;
        evidence_refs: string[];
        model?: string;
      }>>(`/api/solution-workspace/projects/${projectId}/rewrite-section`, input);
      return response.data.data;
    },
  });
}

export function useExtractSolutionRequirements(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { document_ids: string[]; replace_existing?: boolean }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<{
        project: SolutionProject;
        extracted_count: number;
        degraded: boolean;
      }>>(`/api/solution-workspace/projects/${projectId}/extract-requirements`, input);
      return response.data.data;
    },
    onSuccess: ({ project }) => {
      queryClient.setQueryData<SolutionProject[]>(PROJECTS_KEY, (current = []) =>
        current.map((item) => (item.id === project.id ? project : item)),
      );
    },
  });
}

export function useSaveSolutionProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: SolutionProductOption & { model_code: string; product_name: string }) => {
      const response = await httpClient.post<ApiEnvelope<SolutionProductOption>>(
        '/api/solution-workspace/products',
        input,
      );
      return response.data.data;
    },
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: ['solution-workspace', 'context-options', 'v1'],
    }),
  });
}

export function useCreateTenderFromSolution(projectId: string | null) {
  return useMutation({
    mutationFn: async () => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<{ id: number }>>(
        `/api/solution-workspace/projects/${projectId}/create-tender`,
      );
      return response.data.data;
    },
  });
}

export function useSolutionFeedback(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      section_id?: string;
      rating?: number;
      change_type: 'accepted' | 'edited' | 'rejected' | 'other';
      note?: string;
      original_content?: string;
      revised_content?: string;
    }) => {
      if (!projectId) throw new Error('请先创建或选择方案项目');
      const response = await httpClient.post<ApiEnvelope<Record<string, unknown>>>(
        `/api/solution-workspace/projects/${projectId}/feedback`,
        input,
      );
      return response.data.data;
    },
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: ['solution-workspace', 'analytics', 'v1'],
    }),
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

export async function downloadSolution(projectId: string, format: 'markdown' | 'docx' | 'pdf' | 'xlsx') {
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
