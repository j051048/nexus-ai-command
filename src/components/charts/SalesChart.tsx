import React from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend,
  ReferenceLine
} from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { useSalesMetrics } from '@/hooks/useSalesData';
import { useCurrentTargets, SalesTarget } from '@/hooks/useTargets';
import { Skeleton } from '@/components/ui/skeleton';
import { format } from 'date-fns';

// Fallback mock data when no real data exists
const mockSalesData = [
  { month: '1月', leads: 45, conversions: 12, revenue: 128000 },
  { month: '2月', leads: 52, conversions: 15, revenue: 156000 },
  { month: '3月', leads: 48, conversions: 18, revenue: 189000 },
  { month: '4月', leads: 61, conversions: 22, revenue: 234000 },
  { month: '5月', leads: 55, conversions: 19, revenue: 198000 },
  { month: '6月', leads: 67, conversions: 28, revenue: 312000 },
  { month: '7月', leads: 72, conversions: 31, revenue: 356000 },
];

const chartConfig = {
  leads: {
    label: "线索数",
    color: "hsl(var(--primary))",
  },
  conversions: {
    label: "转化数",
    color: "hsl(var(--success))",
  },
};

export function SalesChart() {
  const { data: rawData, isLoading, error } = useSalesMetrics(7);
  const { data: targets } = useCurrentTargets();

  // Get monthly target values
  const monthlyTarget = React.useMemo(() => {
    const data = (targets || []) as SalesTarget[];
    const monthly = data.find((t: SalesTarget) => t.target_type === 'monthly');
    return {
      leads: monthly?.leads_target || 0,
      conversions: monthly?.conversions_target || 0,
    };
  }, [targets]);

  // Transform raw data into monthly aggregates
  const salesData = React.useMemo(() => {
    const data = Array.isArray(rawData) ? rawData : [];
    if (data.length === 0) return mockSalesData;

    const monthMap = new Map<string, { leads: number; conversions: number; revenue: number }>();

    data.forEach((item) => {
      // Ensure date is valid before formatting
      const dateObj = item.date ? new Date(item.date) : new Date();
      if (isNaN(dateObj.getTime())) return;

      const monthKey = format(dateObj, 'M月');
      const current = monthMap.get(monthKey) || { leads: 0, conversions: 0, revenue: 0 };
      monthMap.set(monthKey, {
        leads: current.leads + (item.leads_count || 0),
        conversions: current.conversions + (item.conversions || 0),
        revenue: current.revenue + (Number(item.revenue) || 0),
      });
    });

    if (monthMap.size === 0) return mockSalesData;

    return Array.from(monthMap.entries()).map(([month, data]) => ({
      month,
      ...data,
    }));
  }, [rawData]);

  if (isLoading) {
    return (
      <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
        <Skeleton className="h-6 w-32 mb-2" />
        <Skeleton className="h-4 w-48 mb-6" />
        <Skeleton className="h-[250px] sm:h-[300px] w-full" />
      </div>
    );
  }

  const hasRealData = rawData && rawData.length > 0;
  const hasTargets = monthlyTarget.leads > 0 || monthlyTarget.conversions > 0;

  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">销售趋势</h3>
          <p className="text-sm text-muted-foreground">
            线索与转化月度趋势
            {!hasRealData && <span className="text-warning ml-2">(示例数据)</span>}
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-muted-foreground">线索</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-success" />
            <span className="text-muted-foreground">转化</span>
          </div>
          {hasTargets && (
            <div className="flex items-center gap-2">
              <div className="w-4 h-0.5 bg-muted-foreground" style={{ borderTop: '2px dashed' }} />
              <span className="text-muted-foreground">目标线</span>
            </div>
          )}
        </div>
      </div>
      
      <ChartContainer config={chartConfig} className="h-[250px] sm:h-[300px] w-full">
        <AreaChart data={salesData}>
          <defs>
            <linearGradient id="leadsGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="conversionsGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--success))" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="hsl(var(--success))" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis 
            dataKey="month" 
            className="text-xs" 
            tick={{ fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis 
            className="text-xs" 
            tick={{ fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ChartTooltipContent />} />
          {monthlyTarget.leads > 0 && (
            <ReferenceLine 
              y={monthlyTarget.leads} 
              stroke="hsl(var(--primary))" 
              strokeDasharray="5 5" 
              strokeOpacity={0.6}
              label={{ 
                value: `线索目标 ${monthlyTarget.leads}`, 
                fill: 'hsl(var(--primary))', 
                fontSize: 10,
                position: 'right'
              }}
            />
          )}
          {monthlyTarget.conversions > 0 && (
            <ReferenceLine 
              y={monthlyTarget.conversions} 
              stroke="hsl(var(--success))" 
              strokeDasharray="5 5" 
              strokeOpacity={0.6}
              label={{ 
                value: `转化目标 ${monthlyTarget.conversions}`, 
                fill: 'hsl(var(--success))', 
                fontSize: 10,
                position: 'right'
              }}
            />
          )}
          <Area 
            type="monotone" 
            dataKey="leads" 
            stroke="hsl(var(--primary))" 
            strokeWidth={2}
            fill="url(#leadsGradient)" 
            name="线索数"
          />
          <Area 
            type="monotone" 
            dataKey="conversions" 
            stroke="hsl(var(--success))" 
            strokeWidth={2}
            fill="url(#conversionsGradient)" 
            name="转化数"
          />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
