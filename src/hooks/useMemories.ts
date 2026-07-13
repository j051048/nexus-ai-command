import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { httpClient } from '@/lib/httpClient';

export type MemoryState =
  | 'proposed'
  | 'confirmed'
  | 'active'
  | 'pending_review'
  | 'expired'
  | 'rejected'
  | 'archived';

export type MemoryVisibility = 'private' | 'team' | 'organization';

export interface MemoryRecord {
  id: string;
  key: string;
  value: string;
  category: string;
  importance: number;
  confidence?: number;
  visibility: MemoryVisibility;
  lifecycle_state: MemoryState;
  sensitivity?: 'public' | 'internal' | 'confidential' | 'restricted';
  provenance?: {
    source?: string;
    extraction_method?: string;
    recorded_at?: string;
    evidence_ref?: string;
  };
  evidence_ref?: string;
  expires_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateMemoryInput {
  key: string;
  value: string;
  category: string;
  visibility: MemoryVisibility;
  importance?: number;
  confidence?: number;
  expires_at?: string;
  evidence_ref?: string;
}

export function useMemories() {
  return useQuery({
    queryKey: ['memories', 'all'],
    queryFn: async () => {
      const response = await httpClient.get('/api/memories', {
        params: { state: 'all', limit: 100 },
      });
      return (response.data?.data ?? []) as MemoryRecord[];
    },
  });
}

export function useCreateMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateMemoryInput) => {
      const response = await httpClient.post('/api/memories', input);
      return response.data?.data as MemoryRecord;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memories'] }),
  });
}

export function useUpdateMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: Partial<MemoryRecord> & { id: string }) => {
      const response = await httpClient.patch(`/api/memories/${id}`, input);
      return response.data?.data as MemoryRecord;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memories'] }),
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => httpClient.delete(`/api/memories/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['memories'] }),
  });
}

