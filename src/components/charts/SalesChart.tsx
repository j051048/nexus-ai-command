import React from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend 
} from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';

const salesData = [
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
  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">销售趋势</h3>
          <p className="text-sm text-muted-foreground">线索与转化月度趋势</p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-muted-foreground">线索</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-success" />
            <span className="text-muted-foreground">转化</span>
          </div>
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
