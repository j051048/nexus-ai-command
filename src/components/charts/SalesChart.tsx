import React from 'react';
import { Area, AreaChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import { format } from 'date-fns';

import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { Skeleton } from '@/components/ui/skeleton';
import { SalesTarget, useCurrentTargets } from '@/hooks/useTargets';
import { useSalesMetrics } from '@/hooks/useSalesData';

const chartConfig = {
  leads: { label: '线索数', color: 'hsl(var(--primary))' },
  conversions: { label: '转化数', color: 'hsl(var(--success))' },
};

export function SalesChart() {
  const { data: rawData, isLoading } = useSalesMetrics(7);
  const { data: targets } = useCurrentTargets();

  const monthlyTarget = React.useMemo(() => {
    const data = (targets || []) as SalesTarget[];
    const monthly = data.find((target) => target.target_type === 'monthly');
    return {
      leads: monthly?.leads_target || 0,
      conversions: monthly?.conversions_target || 0,
    };
  }, [targets]);

  const salesData = React.useMemo(() => {
    const data = Array.isArray(rawData) ? rawData : [];
    const monthMap = new Map<string, { leads: number; conversions: number; revenue: number }>();

    data.forEach((item) => {
      const dateObj = item.date ? new Date(item.date) : null;
      if (!dateObj || Number.isNaN(dateObj.getTime())) return;
      const monthKey = format(dateObj, 'M月');
      const current = monthMap.get(monthKey) || { leads: 0, conversions: 0, revenue: 0 };
      monthMap.set(monthKey, {
        leads: current.leads + (item.leads_count || 0),
        conversions: current.conversions + (item.conversions || 0),
        revenue: current.revenue + (Number(item.revenue) || 0),
      });
    });

    return Array.from(monthMap.entries()).map(([month, value]) => ({ month, ...value }));
  }, [rawData]);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <Skeleton className="mb-2 h-6 w-32" />
        <Skeleton className="mb-6 h-4 w-48" />
        <Skeleton className="h-[250px] w-full sm:h-[300px]" />
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">销售趋势</h3>
          <p className="text-sm text-muted-foreground">线索与转化的月度趋势</p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-primary" />
            <span className="text-muted-foreground">线索</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-success" />
            <span className="text-muted-foreground">转化</span>
          </div>
        </div>
      </div>

      {salesData.length === 0 ? (
        <div className="flex h-[250px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground sm:h-[300px]">
          暂无真实销售数据
        </div>
      ) : (
        <ChartContainer config={chartConfig} className="h-[250px] w-full sm:h-[300px]">
          <AreaChart data={salesData}>
            <defs>
              <linearGradient id="leadsGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="conversionsGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--success))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--success))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="month" tick={{ fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
            <Tooltip content={<ChartTooltipContent />} />
            {monthlyTarget.leads > 0 && (
              <ReferenceLine y={monthlyTarget.leads} stroke="hsl(var(--primary))" strokeDasharray="5 5" strokeOpacity={0.6} />
            )}
            {monthlyTarget.conversions > 0 && (
              <ReferenceLine y={monthlyTarget.conversions} stroke="hsl(var(--success))" strokeDasharray="5 5" strokeOpacity={0.6} />
            )}
            <Area type="monotone" dataKey="leads" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#leadsGradient)" name="线索数" />
            <Area type="monotone" dataKey="conversions" stroke="hsl(var(--success))" strokeWidth={2} fill="url(#conversionsGradient)" name="转化数" />
          </AreaChart>
        </ChartContainer>
      )}
    </div>
  );
}
