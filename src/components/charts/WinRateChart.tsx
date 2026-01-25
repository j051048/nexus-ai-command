import React from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useWinRateHistory } from '@/hooks/useSalesData';
import { useCurrentTargets } from '@/hooks/useTargets';
import { Skeleton } from '@/components/ui/skeleton';

// Fallback mock data
const mockWinRateData = [
  { week: '第1周', rate: 18, target: 25 },
  { week: '第2周', rate: 22, target: 25 },
  { week: '第3周', rate: 21, target: 25 },
  { week: '第4周', rate: 26, target: 25 },
  { week: '第5周', rate: 24, target: 25 },
  { week: '第6周', rate: 28, target: 25 },
  { week: '第7周', rate: 32, target: 25 },
  { week: '第8周', rate: 29, target: 25 },
];

const chartConfig = {
  rate: {
    label: "赢率",
    color: "hsl(var(--primary))",
  },
  target: {
    label: "目标",
    color: "hsl(var(--muted-foreground))",
  },
};

export function WinRateChart() {
  const { data: rawData, isLoading } = useWinRateHistory(8);
  const { data: targets } = useCurrentTargets();

  // Get monthly target win rate
  const targetWinRate = React.useMemo(() => {
    const monthly = targets?.find(t => t.target_type === 'monthly');
    return monthly?.win_rate_target || 25; // Default to 25% if no target
  }, [targets]);

  const winRateData = React.useMemo(() => {
    if (!rawData || rawData.length === 0) return mockWinRateData;
    return rawData;
  }, [rawData]);

  const currentRate = winRateData[winRateData.length - 1]?.rate || 0;
  const previousRate = winRateData[winRateData.length - 2]?.rate || 0;
  const change = currentRate - previousRate;
  const isUp = change >= 0;
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
          <h3 className="text-lg font-semibold text-foreground">赢率变化曲线</h3>
          <p className="text-sm text-muted-foreground">
            近8周销售赢率趋势
            {!hasRealData && <span className="text-warning ml-2">(示例数据)</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary">
          <span className="text-2xl font-bold text-foreground mono-number">{currentRate}%</span>
          <div className={`flex items-center gap-1 text-sm ${isUp ? 'text-success' : 'text-destructive'}`}>
            {isUp ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            <span>{isUp ? '+' : ''}{change}%</span>
          </div>
        </div>
      </div>

      <ChartContainer config={chartConfig} className="h-[200px] sm:h-[250px] w-full">
        <LineChart data={winRateData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis 
            dataKey="week" 
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis 
            domain={[0, Math.max(40, targetWinRate + 10)]}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip 
            content={<ChartTooltipContent />}
            formatter={(value: number) => [`${value}%`, '赢率']}
          />
          <ReferenceLine 
            y={targetWinRate} 
            stroke="hsl(var(--muted-foreground))" 
            strokeDasharray="5 5" 
            label={{ 
              value: `目标 ${targetWinRate}%`, 
              fill: 'hsl(var(--muted-foreground))', 
              fontSize: 11 
            }}
          />
          <Line 
            type="monotone" 
            dataKey="rate" 
            stroke="hsl(var(--primary))" 
            strokeWidth={3}
            dot={{ fill: 'hsl(var(--primary))', strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6, fill: 'hsl(var(--primary))', stroke: 'hsl(var(--background))', strokeWidth: 2 }}
          />
        </LineChart>
      </ChartContainer>

      <div className="flex items-center justify-center gap-6 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-1 rounded bg-primary" />
          <span className="text-muted-foreground">实际赢率</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-0.5 bg-muted-foreground" style={{ borderTop: '2px dashed' }} />
          <span className="text-muted-foreground">目标线</span>
        </div>
      </div>
    </div>
  );
}
