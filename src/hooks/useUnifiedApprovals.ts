import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

export interface UnifiedApprovalItem {
  id: string;
  source_table: 'approval_requests' | 'oa_leave_requests';
  type: string;
  description: string;
  amount: number | null;
  status: string;
  submitted_by: string;
  submitter_name: string | null;
  created_at: string;
  leave_type?: string;
  start_date?: string;
  end_date?: string;
  days?: number;
}

interface UnifiedApprovalListResponse {
  items: UnifiedApprovalItem[];
  total: number;
  page: number;
  page_size: number;
}

export function useUnifiedApprovals(
  tab: 'pending' | 'mine' | 'handled',
  typeFilter?: string,
  page: number = 1,
) {
  return useQuery({
    queryKey: ['unified-approvals', tab, typeFilter, page],
    queryFn: async (): Promise<UnifiedApprovalListResponse> => {
      const params = new URLSearchParams({ tab, page: String(page) });
      if (typeFilter) params.set('type_filter', typeFilter);
      const result = await aiClient.fetch(`api/approval/list?${params}`);
      return result?.data || { items: [], total: 0, page: 1, page_size: 20 };
    },
  });
}

export function useTabCounts() {
  return useQuery({
    queryKey: ['approval-tab-counts'],
    queryFn: async (): Promise<{ pending: number; mine: number }> => {
      const result = await aiClient.fetch('api/approval/tab-counts');
      return result?.data || { pending: 0, mine: 0 };
    },
    refetchInterval: 30000,
  });
}
