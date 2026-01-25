import React from 'react';
import { 
  ComposedChart, 
  Bar, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { useRevenueData } from '@/hooks/useSalesData';
import { Skeleton } from '@/components/ui/skeleton';

// Fallback mock data
const mockRevenueData = [
  { month: '1月', revenue: 128, target: 120, growth: 8 },
  { month: '2月', revenue: 156, target: 130, growth: 22 },
  { month: '3月', revenue: 189, target: 150, growth: 21 },
  { month: '4月', revenue: 234, target: 180, growth: 24 },
  { month: '5月', revenue: 198, target: 200, growth: -15 },
  { month: '6月', revenue: 312, target: 220, growth: 58 },
  { month: '7月', revenue: 356, target: 280, growth: 14 },
];

const chartConfig = {
  revenue: {
    label: "营收(万)",
    color: "hsl(var(--primary))",
  },
  target: {
    label: "目标(万)",
    color: "hsl(var(--muted-foreground))",
  },
};

export function RevenueChart() {
  const { data: rawData, isLoading } = useRevenueData(7);

  const revenueData = React.useMemo(() => {
    if (!rawData || rawData.length === 0) return mockRevenueData;
    return rawData;
  }, [rawData]);

  const totalRevenue = revenueData.reduce((sum, d) => sum + d.revenue, 0);
  const totalTarget = revenueData.reduce((sum, d) => sum + d.target, 0);
  const completion = totalTarget > 0 ? Math.round((totalRevenue / totalTarget) * 100) : 0;
  const hasRealData = rawData && rawData.length > 0;

  if (isLoading) {
    return (
      <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
        <Skeleton className="h-6 w-32 mb-2" />
        <Skeleton className="h-4 w-48 mb-6" />
        <Skeleton className="h-[200px] sm:h-[250px] w-full" />
      </div>
    );
  }

  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">营收分析</h3>
          <p className="text-sm text-muted-foreground">
            月度营收与目标对比
            {!hasRealData && <span className="text-warning ml-2">(示例数据)</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-xs text-muted-foreground">累计营收</p>
            <p className="text-xl font-bold text-foreground mono-number">¥{totalRevenue}万</p>
          </div>
          <div className="w-px h-10 bg-border" />
          <div className="text-right">
            <p className="text-xs text-muted-foreground">目标完成</p>
            <p className={`text-xl font-bold mono-number ${completion >= 100 ? 'text-success' : 'text-warning'}`}>
              {completion}%
            </p>
          </div>
        </div>
      </div>

      <ChartContainer config={chartConfig} className="h-[200px] sm:h-[250px] w-full">
        <ComposedChart data={revenueData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis 
            dataKey="month" 
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis 
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => `${value}万`}
          />
          <Tooltip 
            content={<ChartTooltipContent />}
            formatter={(value: number, name: string) => [
              `¥${value}万`, 
              name === 'revenue' ? '实际营收' : '目标'
            ]}
          />
          <Bar 
            dataKey="revenue" 
            fill="hsl(var(--primary))" 
            radius={[4, 4, 0, 0]}
            barSize={32}
          />
          <Line 
            type="monotone" 
            dataKey="target" 
            stroke="hsl(var(--muted-foreground))" 
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
          />
        </ComposedChart>
      </ChartContainer>

      <div className="flex items-center justify-center gap-6 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-3 rounded-sm bg-primary" />
          <span className="text-muted-foreground">实际营收</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-muted-foreground" style={{ borderTop: '2px dashed' }} />
          <span className="text-muted-foreground">目标线</span>
        </div>
      </div>
    </div>
  );
}
