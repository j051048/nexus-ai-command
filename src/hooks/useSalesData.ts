import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format, startOfWeek, subDays, subWeeks } from 'date-fns';
import { toast } from 'sonner';

import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { httpClient } from '@/lib/httpClient';

export interface SalesMetric {
  id: string;
  user_id: string | null;
  date: string;
  leads_count: number | null;
  conversions: number | null;
  revenue: number | null;
  win_rate: number | null;
  calls_made: number | null;
  score: number | null;
  created_at: string | null;
}

export interface TeamPerformanceData {
  id: string;
  week_start: string;
  total_leads: number | null;
  total_conversions: number | null;
  total_revenue: number | null;
  avg_win_rate: number | null;
  top_performer_id: string | null;
  created_at: string | null;
}

export interface TeamMemberPerformance {
  name: string;
  score: number;
  bonus: number;
  calls: number;
  conversions: number;
  user_id: string;
}

export function useSalesMetricsRealtime() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  useQuery({
    queryKey: ['sales-metrics-realtime-poll', session?.user?.id],
    queryFn: async () => {
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
      queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
      queryClient.invalidateQueries({ queryKey: ['team-performance'] });
      return null;
    },
    enabled: !!session?.user?.id,
    refetchInterval: 30000,
  });
}

export function useSalesMetrics(months: number = 7) {
  const { session } = useAuth();

  return useQuery({
    queryKey: ['sales-metrics', session?.user?.id, months],
    queryFn: async () => {
      if (!session?.user?.id) return [];
      const startDate = format(subDays(new Date(), months * 30), 'yyyy-MM-dd');
      const endDate = format(new Date(), 'yyyy-MM-dd');
      const response = await httpClient.get('/api/sales/metrics/range', {
        params: { start_date: startDate, end_date: endDate },
      });
      const result = response.data?.data;
      return (Array.isArray(result) ? result : []) as SalesMetric[];
    },
    enabled: !!session?.user?.id,
  });
}

export function useSalesMetricsByRange(startDate: string | null, endDate: string | null) {
  const { session, role, profile } = useAuth();

  return useQuery({
    queryKey: ['sales-metrics-range', session?.user?.id, role, startDate, endDate],
    queryFn: async () => {
      if (!session?.user?.id || !startDate || !endDate) return [];
      const params: Record<string, string> = { start_date: startDate, end_date: endDate };
      if (role !== 'boss') params.target_user_id = session.user.id;
      const response = await httpClient.get('/api/sales/metrics/range', { params });
      const result = response.data?.data;
      return (Array.isArray(result) ? result : []) as SalesMetric[];
    },
    enabled: !!session?.user?.id && !!startDate && !!endDate && !!profile?.organization_id,
  });
}

export function useWinRateHistory(weeks: number = 8) {
  const { session } = useAuth();

  return useQuery({
    queryKey: ['win-rate-history', session?.user?.id, weeks],
    queryFn: async () => {
      if (!session?.user?.id) return [];
      const startDate = format(subWeeks(new Date(), weeks), 'yyyy-MM-dd');
      const endDate = format(new Date(), 'yyyy-MM-dd');
      const response = await httpClient.get('/api/sales/metrics/range', {
        params: { start_date: startDate, end_date: endDate, target_user_id: session.user.id },
      });
      const raw = response.data?.data;
      const data = (Array.isArray(raw) ? raw : []) as Array<{ date: string; win_rate: number | null }>;
      const weekMap = new Map<string, number[]>();

      data.forEach((item) => {
        const weekStart = format(startOfWeek(new Date(item.date), { weekStartsOn: 1 }), 'yyyy-MM-dd');
        const rates = weekMap.get(weekStart) || [];
        if (item.win_rate !== null) rates.push(Number(item.win_rate));
        weekMap.set(weekStart, rates);
      });

      return Array.from(weekMap.entries()).map(([, rates], index) => ({
        week: `第 ${index + 1} 周`,
        rate: rates.length ? Math.round(rates.reduce((sum, rate) => sum + rate, 0) / rates.length) : 0,
        target: 25,
      }));
    },
    enabled: !!session?.user?.id,
  });
}

export function useRevenueData(months: number = 7) {
  const { session, role, profile } = useAuth();

  return useQuery({
    queryKey: ['revenue-data', session?.user?.id, role, months, profile?.organization_id],
    queryFn: async () => {
      if (!session?.user?.id) return [];
      const startDate = format(subDays(new Date(), months * 30), 'yyyy-MM-dd');
      const endDate = format(new Date(), 'yyyy-MM-dd');
      const params: Record<string, string> = { start_date: startDate, end_date: endDate };
      if (role !== 'boss') params.target_user_id = session.user.id;
      const response = await httpClient.get('/api/sales/metrics/range', { params });
      const raw = response.data?.data;
      const data = (Array.isArray(raw) ? raw : []) as Array<{ date: string; revenue: number | null }>;
      const monthMap = new Map<string, number>();
      const targetPerMonth = 150;

      data.forEach((item) => {
        const monthKey = format(new Date(item.date), 'M月');
        monthMap.set(monthKey, (monthMap.get(monthKey) || 0) + (Number(item.revenue) || 0));
      });

      return Array.from(monthMap.entries()).map(([month, revenue]) => ({
        month,
        revenue: Math.round(revenue / 10000),
        target: targetPerMonth,
        growth: 0,
      }));
    },
    enabled: !!session?.user?.id,
  });
}

export function useTeamPerformance() {
  const { session, role, profile } = useAuth();

  return useQuery({
    queryKey: ['team-performance', session?.user?.id, profile?.organization_id],
    queryFn: async () => {
      if (!session?.user?.id || !profile?.organization_id) return [];
      const response = await httpClient.get('/api/sales/team-performance');
      const result = response.data?.data;
      return (Array.isArray(result) ? result : []) as TeamMemberPerformance[];
    },
    enabled: !!session?.user?.id && role === 'boss' && !!profile?.organization_id,
  });
}

export function useLeaderboard(limit: number = 5) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['leaderboard', limit, profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];
      const response = await httpClient.get('/api/sales/leaderboard', { params: { limit } });
      const data = Array.isArray(response.data?.data) ? response.data.data : [];
      return data.map((person: { id: string; name: string; score: number | null; total_bonus: number | null }, index: number) => ({
        rank: index + 1,
        name: person.name,
        score: person.score || 0,
        bonus: Number(person.total_bonus) || 0,
        trend: 'stable' as const,
        isCurrentUser: person.id === session?.user?.id,
      }));
    },
    enabled: !!session?.user?.id && !!profile?.organization_id,
  });
}

export function useSaveSalesMetric() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async (metric: {
      leads_count?: number;
      conversions?: number;
      revenue?: number;
      win_rate?: number;
      calls_made?: number;
      score?: number;
      date?: string;
    }) => {
      if (!session?.user?.id) throw new Error('Not authenticated');
      const response = await httpClient.post('/api/sales/metrics', {
        user_id: session.user.id,
        date: metric.date || format(new Date(), 'yyyy-MM-dd'),
        leads_count: metric.leads_count || 0,
        conversions: metric.conversions || 0,
        revenue: metric.revenue || 0,
        win_rate: metric.win_rate || 0,
        calls_made: metric.calls_made || 0,
        score: metric.score || 0,
      });
      return response.data?.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
      queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
      queryClient.invalidateQueries({ queryKey: ['team-performance'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
      toast.success('销售数据已保存');
    },
    onError: (err: Error) => {
      toast.error(err.message || '保存销售数据失败');
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async (updates: { score?: number; total_bonus?: number; rank?: number }) => {
      if (!session?.user?.id) throw new Error('Not authenticated');
      const { data, error } = await supabase.from('profiles').update(updates).eq('user_id', session.user.id).select().single();
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
      queryClient.invalidateQueries({ queryKey: ['team-performance'] });
    },
    onError: (err: Error) => {
      toast.error(err.message || '更新个人信息失败');
    },
  });
}

export function useSeedDemoData() {
  return useMutation({
    mutationFn: async () => {
      throw new Error('生产版本已禁用演示数据生成');
    },
  });
}

export function exportToCSV(data: SalesMetric[], filename: string = 'sales-report') {
  if (!data || data.length === 0) {
    throw new Error('No data to export');
  }

  const headers = ['日期', '线索数', '转化数', '营收', '赢率%', '通话数', '绩效分'];
  const rows = data.map((row) => [
    row.date,
    row.leads_count || 0,
    row.conversions || 0,
    row.revenue || 0,
    row.win_rate || 0,
    row.calls_made || 0,
    row.score || 0,
  ]);
  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${filename}-${format(new Date(), 'yyyy-MM-dd')}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}
