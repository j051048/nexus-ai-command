import React from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts';
import { TrendingDown, TrendingUp } from 'lucide-react';

import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { Skeleton } from '@/components/ui/skeleton';
import { useWinRateHistory } from '@/hooks/useSalesData';
import { SalesTarget, useCurrentTargets } from '@/hooks/useTargets';

const chartConfig = {
  rate: { label: '赢率', color: 'hsl(var(--primary))' },
  target: { label: '目标', color: 'hsl(var(--muted-foreground))' },
};

export function WinRateChart() {
  const { data: rawData, isLoading } = useWinRateHistory(8);
  const { data: targets } = useCurrentTargets();

  const targetWinRate = React.useMemo(() => {
    const data = (targets || []) as SalesTarget[];
    const monthly = data.find((target) => target.target_type === 'monthly');
    return monthly?.win_rate_target || 25;
  }, [targets]);

  const winRateData = Array.isArray(rawData) ? rawData : [];
  const currentRate = winRateData[winRateData.length - 1]?.rate || 0;
  const previousRate = winRateData[winRateData.length - 2]?.rate || 0;
  const change = currentRate - previousRate;
  const isUp = change >= 0;

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
        <Skeleton className="mb-2 h-6 w-32" />
        <Skeleton className="mb-6 h-4 w-48" />
        <Skeleton className="h-[200px] w-full sm:h-[250px]" />
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-4 sm:p-6">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">赢率变化曲线</h3>
          <p className="text-sm text-muted-foreground">最近 8 周销售赢率趋势</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-1.5">
          <span className="mono-number text-2xl font-bold text-foreground">{currentRate}%</span>
          <div className={`flex items-center gap-1 text-sm ${isUp ? 'text-success' : 'text-destructive'}`}>
            {isUp ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
            <span>{isUp ? '+' : ''}{change}%</span>
          </div>
        </div>
      </div>

      {winRateData.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground sm:h-[250px]">
          暂无真实赢率数据
        </div>
      ) : (
        <ChartContainer config={chartConfig} className="h-[200px] w-full sm:h-[250px]">
          <LineChart data={winRateData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="week" tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[0, Math.max(40, targetWinRate + 10)]}
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `${value}%`}
            />
            <Tooltip content={<ChartTooltipContent />} formatter={(value: number) => [`${value}%`, '赢率']} />
            <ReferenceLine
              y={targetWinRate}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="5 5"
              label={{ value: `目标 ${targetWinRate}%`, fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
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
      )}
    </div>
  );
}
