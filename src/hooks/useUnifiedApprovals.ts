import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';
import { type ApiPayload, unwrapApiData } from '@/api/response';
import { useEnterpriseQueryScope } from '@/hooks/useEnterpriseQueryScope';

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
  const scope = useEnterpriseQueryScope();
  return useQuery({
    queryKey: ['unified-approvals', tab, typeFilter, page, ...scope.key],
    enabled: scope.enabled,
    queryFn: async ({ signal }): Promise<UnifiedApprovalListResponse> => {
      const params = new URLSearchParams({ tab, page: String(page) });
      if (typeFilter) params.set('type_filter', typeFilter);
      const result = await aiClient.fetch<ApiPayload<UnifiedApprovalListResponse>>(`api/approval/list?${params}`, scope.options(signal));
      const data = unwrapApiData(result);
      if (!data || !Array.isArray(data.items)) throw new Error('审批数据格式异常，请重试');
      return data;
    },
  });
}

export function useTabCounts() {
  const scope = useEnterpriseQueryScope();
  return useQuery({
    queryKey: ['approval-tab-counts', ...scope.key],
    enabled: scope.enabled,
    queryFn: async ({ signal }): Promise<{ pending: number; mine: number }> => {
      const result = await aiClient.fetch<ApiPayload<{ pending: number; mine: number }>>('api/approval/tab-counts', scope.options(signal));
      const data = unwrapApiData(result);
      if (!data || typeof data.pending !== 'number' || typeof data.mine !== 'number') {
        throw new Error('审批数量格式异常，请重试');
      }
      return data;
    },
    refetchInterval: 30000,
  });
}
