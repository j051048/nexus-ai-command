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

const winRateData = [
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
  const currentRate = winRateData[winRateData.length - 1].rate;
  const previousRate = winRateData[winRateData.length - 2].rate;
  const change = currentRate - previousRate;
  const isUp = change >= 0;

  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">赢率变化曲线</h3>
          <p className="text-sm text-muted-foreground">近8周销售赢率趋势</p>
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
            domain={[0, 40]}
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
            y={25} 
            stroke="hsl(var(--muted-foreground))" 
            strokeDasharray="5 5" 
            label={{ value: '目标 25%', fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
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
    </div>
  );
}
