import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

export function useOptimisticUpdate<T>(
  queryKey: string[],
  mutationFn: (data: T) => Promise<T>
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onMutate: async (newData) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, newData);
      return { previous };
    },
    onError: (err, newData, context) => {
      queryClient.setQueryData(queryKey, context?.previous);
      toast.error('操作失败，已回滚');
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
}
