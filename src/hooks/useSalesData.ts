import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';
import { format, subDays, startOfWeek, subWeeks } from 'date-fns';
import { toast } from 'sonner';
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

// Hook for real-time subscription to sales metrics — replaced with polling
export function useSalesMetricsRealtime() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  useQuery({
    queryKey: ['sales-metrics-realtime-poll', session?.user?.id],
    queryFn: async () => {
      // Invalidate all related queries to refetch fresh data
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
      queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
      queryClient.invalidateQueries({ queryKey: ['team-performance'] });
      return null;
    },
    enabled: !!session?.user?.id,
    refetchInterval: 30000, // 30 seconds
  });
}

// Fetch user's sales metrics for the last N months
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

// Fetch sales metrics by date range
export function useSalesMetricsByRange(startDate: string | null, endDate: string | null) {
  const { session, role, profile } = useAuth();

  return useQuery({
    queryKey: ['sales-metrics-range', session?.user?.id, role, startDate, endDate],
    queryFn: async () => {
      if (!session?.user?.id || !startDate || !endDate) return [];

      const params: Record<string, string> = {
        start_date: startDate,
        end_date: endDate,
      };

      // If not boss, request own metrics only
      if (role !== 'boss') {
        params.target_user_id = session.user.id;
      }

      const response = await httpClient.get('/api/sales/metrics/range', { params });
      const result = response.data?.data;
      return (Array.isArray(result) ? result : []) as SalesMetric[];
    },
    enabled: !!session?.user?.id && !!startDate && !!endDate && !!profile?.organization_id,
  });
}

// Fetch win rate data by week for the last N weeks
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

      // Group by week and calculate average win rate per week
      const weeklyData: { week: string; rate: number; target: number }[] = [];
      const weekMap = new Map<string, number[]>();

      data.forEach((item) => {
        const weekStart = format(startOfWeek(new Date(item.date), { weekStartsOn: 1 }), 'yyyy-MM-dd');
        if (!weekMap.has(weekStart)) {
          weekMap.set(weekStart, []);
        }
        if (item.win_rate !== null) {
          weekMap.get(weekStart)!.push(Number(item.win_rate));
        }
      });

      let weekNum = 1;
      weekMap.forEach((rates, _weekStart) => {
        const avgRate = rates.length > 0
          ? Math.round(rates.reduce((a, b) => a + b, 0) / rates.length)
          : 0;
        weeklyData.push({
          week: `第${weekNum}周`,
          rate: avgRate,
          target: 25,
        });
        weekNum++;
      });

      return weeklyData;
    },
    enabled: !!session?.user?.id,
  });
}

// Fetch monthly revenue data
export function useRevenueData(months: number = 7) {
  const { session, role, profile } = useAuth();

  return useQuery({
    queryKey: ['revenue-data', session?.user?.id, role, months, profile?.organization_id],
    queryFn: async () => {
      if (!session?.user?.id) return [];

      const startDate = format(subDays(new Date(), months * 30), 'yyyy-MM-dd');

      const endDate = format(new Date(), 'yyyy-MM-dd');
      const params: Record<string, string> = { start_date: startDate, end_date: endDate };
      if (role !== 'boss') {
        params.target_user_id = session.user.id;
      }

      const response = await httpClient.get('/api/sales/metrics/range', { params });
      const raw = response.data?.data;
      const data = (Array.isArray(raw) ? raw : []) as Array<{ date: string; revenue: number | null }>;

      // Group by month
      const monthMap = new Map<string, number>();
      const targetPerMonth = 150; // Target in 万

      data.forEach((item) => {
        const monthKey = format(new Date(item.date), 'M月');
        const current = monthMap.get(monthKey) || 0;
        monthMap.set(monthKey, current + (Number(item.revenue) || 0));
      });

      return Array.from(monthMap.entries()).map(([month, revenue]) => ({
        month,
        revenue: Math.round(revenue / 10000), // Convert to 万
        target: targetPerMonth,
        growth: 0, // Could calculate from previous month
      }));
    },
    enabled: !!session?.user?.id,
  });
}

// Fetch team performance data (for boss role)
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

// Fetch leaderboard data
export function useLeaderboard(limit: number = 5) {
  const { session, profile } = useAuth();

  return useQuery({
    queryKey: ['leaderboard', limit, profile?.organization_id],
    queryFn: async () => {
      if (!profile?.organization_id) return [];

      const response = await httpClient.get('/api/sales/leaderboard', {
        params: { limit },
      });

      const data = Array.isArray(response.data?.data) ? response.data.data : [];
      return data.map((p: { id: string; name: string; score: number | null; total_bonus: number | null; rank: number | null }, index: number) => ({
        rank: index + 1,
        name: p.name,
        score: p.score || 0,
        bonus: Number(p.total_bonus) || 0,
        trend: 'stable' as const,
        isCurrentUser: p.id === session?.user?.id,
      }));
    },
    enabled: !!session?.user?.id && !!profile?.organization_id,
  });
}

// Save daily sales metrics (with upsert to handle existing dates)
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

// Update user's profile score and bonus — kept with supabase (special operation)
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async (updates: {
      score?: number;
      total_bonus?: number;
      rank?: number;
    }) => {
      if (!session?.user?.id) throw new Error('Not authenticated');

      const { data, error } = await supabase
        .from('profiles')
        .update(updates)
        .eq('user_id', session.user.id)
        .select()
        .single();

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

// Generate mock data for demo purposes — kept with supabase (special operation)
export function useSeedDemoData() {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  return useMutation({
    mutationFn: async () => {
      if (!session?.user?.id) throw new Error('Not authenticated');

      // Generate last 90 days of sample data
      const records = [];
      for (let i = 90; i >= 0; i--) {
        const date = format(subDays(new Date(), i), 'yyyy-MM-dd');
        records.push({
          user_id: session.user.id,
          date,
          leads_count: Math.floor(Math.random() * 10) + 1,
          conversions: Math.floor(Math.random() * 5),
          revenue: Math.floor(Math.random() * 50000) + 10000,
          win_rate: Math.floor(Math.random() * 30) + 10,
          calls_made: Math.floor(Math.random() * 20) + 5,
          score: Math.floor(Math.random() * 20) + 75,
        });
      }

      const { error } = await supabase
        .from('sales_metrics')
        .upsert(records, { onConflict: 'user_id,date', ignoreDuplicates: true });

      if (error) throw error;
      return { inserted: records.length };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['sales-metrics-range'] });
      queryClient.invalidateQueries({ queryKey: ['win-rate-history'] });
      queryClient.invalidateQueries({ queryKey: ['revenue-data'] });
      toast.success('演示数据已生成');
    },
    onError: (err: Error) => {
      toast.error(err.message || '生成演示数据失败');
    },
  });
}

// Export sales data as CSV
export function exportToCSV(data: SalesMetric[], filename: string = 'sales-report') {
  if (!data || data.length === 0) {
    throw new Error('No data to export');
  }

  const headers = ['日期', '线索数', '转化数', '营收', '赢率%', '通话数', '绩效分'];
  const rows = data.map(row => [
    row.date,
    row.leads_count || 0,
    row.conversions || 0,
    row.revenue || 0,
    row.win_rate || 0,
    row.calls_made || 0,
    row.score || 0,
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${filename}-${format(new Date(), 'yyyy-MM-dd')}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}
