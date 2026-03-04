import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

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
  return useQuery({
    queryKey: ['approval-type-config'],
    queryFn: async (): Promise<ApprovalTypeConfig[]> => {
      const result = await aiClient.fetch('api/approval/type-config');
      return result?.data || [];
    },
    staleTime: 5 * 60 * 1000,
  });
}
