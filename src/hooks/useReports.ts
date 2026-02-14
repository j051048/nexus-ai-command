import { useQuery } from '@tanstack/react-query';
import { aiClient } from '@/api/aiClient';

interface DateRange {
  preset?: string;
  start?: string;
  end?: string;
}

function buildParams(dateRange: DateRange): string {
  const params = new URLSearchParams();
  if (dateRange.preset) params.set('preset', dateRange.preset);
  if (dateRange.start) params.set('start', dateRange.start);
  if (dateRange.end) params.set('end', dateRange.end);
  return params.toString();
}

export function useSalesReport(dateRange: DateRange, groupBy: string = 'day') {
  const qs = buildParams(dateRange);
  return useQuery({
    queryKey: ['report-sales', dateRange, groupBy],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: Record<string, unknown> }>(
        `api/reports/sales?${qs}&group_by=${groupBy}`
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function useApprovalReport(dateRange: DateRange) {
  const qs = buildParams(dateRange);
  return useQuery({
    queryKey: ['report-approvals', dateRange],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: Record<string, unknown> }>(
        `api/reports/approvals?${qs}`
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function usePerformanceReport(dateRange: DateRange) {
  const qs = buildParams(dateRange);
  return useQuery({
    queryKey: ['report-performance', dateRange],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: Record<string, unknown> }>(
        `api/reports/performance?${qs}`
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function useUsageReport(dateRange: DateRange) {
  const qs = buildParams(dateRange);
  return useQuery({
    queryKey: ['report-usage', dateRange],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: Record<string, unknown> }>(
        `api/reports/usage?${qs}`
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function useOverviewStats() {
  return useQuery({
    queryKey: ['report-overview'],
    queryFn: async () => {
      const res = await aiClient.fetch<{ success: boolean; data: Record<string, unknown> }>(
        'api/reports/overview'
      );
      return res.data;
    },
    staleTime: 60_000,
  });
}
