import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

interface SavedPrompt {
  id: string;
  title: string;
  prompt: string;
  icon: string;
  sort_order: number;
  created_at: string;
}

export function useSavedPrompts() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['saved-prompts'],
    queryFn: async () => {
      const res = await aiClient.get<{ data: SavedPrompt[] }>('/api/ai/saved-prompts');
      return res.data;
    },
    staleTime: 2 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: async (data: { title: string; prompt: string; icon?: string; sort_order?: number }) => {
      return aiClient.post('/api/ai/saved-prompts', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-prompts'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      return aiClient.delete(`/api/ai/saved-prompts/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-prompts'] });
    },
  });

  return {
    prompts: query.data ?? [],
    isLoading: query.isLoading,
    savePrompt: createMutation.mutateAsync,
    deletePrompt: deleteMutation.mutateAsync,
    isSaving: createMutation.isPending,
  };
}
