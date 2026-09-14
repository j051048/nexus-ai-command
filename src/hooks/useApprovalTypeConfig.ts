import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { type ApiPayload, unwrapApiList } from '@/api/response';
import { useEnterpriseQueryScope } from '@/hooks/useEnterpriseQueryScope';

export interface ApprovalTypeConfig {
  id: string;
  type_code: string;
  type_name: string;
  icon: string;
  category: string;
  default_chain_key: string | null;
  amount_field: boolean;
  source_table: string;
  sort_order: number;
}

export function useApprovalTypeConfig() {
  const scope = useEnterpriseQueryScope();
  return useQuery({
    queryKey: ['approval-type-config', ...scope.key],
    enabled: scope.enabled,
    queryFn: async ({ signal }): Promise<ApprovalTypeConfig[]> => {
      const result = await aiClient.fetch<ApiPayload<ApprovalTypeConfig[]>>('api/approval/type-config', scope.options(signal));
      return unwrapApiList(result);
    },
    staleTime: 5 * 60 * 1000,
  });
}
