import { useQuery } from '@tanstack/react-query';
import { httpClient } from '@/lib/httpClient';

export interface AIWeeklyReportData {
  generated_at?: string;
  week_start?: string;
  actions_executed: number;
  successful_actions: number;
  success_rate: number;
  human_overrides: number;
  risk_avoided: number;
  failures_by_category: Record<string, number>;
  top_failed_scenarios: Array<{ category: string; count: number }>;
  estimated_hours_saved: number;
  estimated_savings: number;
  audit_summary: string;
  recommendations: string[];
}

const fallbackReport: AIWeeklyReportData = {
  actions_executed: 0,
  successful_actions: 0,
  success_rate: 0,
  human_overrides: 0,
  risk_avoided: 0,
  failures_by_category: {},
  top_failed_scenarios: [],
  estimated_hours_saved: 0,
  estimated_savings: 0,
  audit_summary: 'AI weekly report is waiting for this week activity.',
  recommendations: [],
};

export function useAIWeeklyReport() {
  return useQuery({
    queryKey: ['dashboard', 'ai-weekly-report'],
    queryFn: async () => {
      const response = await httpClient.get('/api/dashboard/ai-weekly-report', {
        headers: { 'X-Silent-Error': '1' },
      });
      return (response.data?.data ?? response.data ?? fallbackReport) as AIWeeklyReportData;
    },
    staleTime: 5 * 60 * 1000,
    retry: 1,
    placeholderData: fallbackReport,
  });
}
