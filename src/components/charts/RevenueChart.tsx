import React from 'react';
import { 
  ComposedChart, 
  Bar, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { useRevenueData } from '@/hooks/useSalesData';
import { useCurrentTargets } from '@/hooks/useTargets';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { TrendingUp } from 'lucide-react';

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
  const { data: targets } = useCurrentTargets();

  // Get monthly revenue target
  const monthlyRevenueTarget = React.useMemo(() => {
    const monthly = targets?.find(t => t.target_type === 'monthly');
    return monthly?.revenue_target ? Number(monthly.revenue_target) / 10000 : 0; // Convert to 万
  }, [targets]);

  const revenueData = React.useMemo(() => {
    if (!rawData || rawData.length === 0) return [];
    // Add target line to each data point if we have a target
    if (monthlyRevenueTarget > 0) {
      return rawData.map(d => ({
        ...d,
        target: monthlyRevenueTarget,
      }));
    }
    return rawData;
  }, [rawData, monthlyRevenueTarget]);

  const totalRevenue = revenueData.reduce((sum, d) => sum + d.revenue, 0);
  const totalTarget = monthlyRevenueTarget > 0 
    ? monthlyRevenueTarget * revenueData.length 
    : revenueData.reduce((sum, d) => sum + (d.target || 0), 0);
  const completion = totalTarget > 0 ? Math.round((totalRevenue / totalTarget) * 100) : 0;

  if (isLoading) {
    return (
      <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
        <Skeleton className="h-6 w-32 mb-2" />
        <Skeleton className="h-4 w-48 mb-6" />
        <Skeleton className="h-[200px] sm:h-[250px] w-full" />
      </div>
    );
  }

  if (revenueData.length === 0) {
    return (
      <div className="relative overflow-hidden card-glass rounded-3xl p-6 sm:p-8 border border-border/50 shadow-2xl h-full flex flex-col items-center justify-center min-h-[300px]">
        <TrendingUp className="w-12 h-12 text-muted-foreground/30 mb-4" />
        <p className="text-sm text-muted-foreground font-medium">暂无营收数据</p>
        <p className="text-xs text-muted-foreground/60 mt-1">录入销售业绩后将自动生成趋势图</p>
      </div>
    );
  }

    return (
        <div className="relative overflow-hidden card-glass rounded-3xl p-6 sm:p-8 border border-border/50 shadow-2xl transition-all duration-300 h-full flex flex-col group">
            <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 blur-[80px] rounded-full pointer-events-none group-hover:bg-primary/20 transition-colors duration-700" />
            
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8 relative z-10">
                <div>
                    <h3 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/80">
                        智能营收预测与追踪
                    </h3>
                    <p className="text-sm font-medium text-muted-foreground mt-1">
                        月度营收与目标对比
                    </p>
                </div>
                <div className="flex items-center gap-6 bg-background/40 backdrop-blur-md px-4 py-3 rounded-2xl border border-border/50 shadow-inner">
                    <div className="text-right">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">累计已确认营收</p>
                        <p className="text-2xl font-extrabold text-foreground mono-number mt-0.5">
                            <span className="text-base text-primary/80 mr-1">¥</span>
                            {totalRevenue}<span className="text-sm text-muted-foreground ml-1">万</span>
                        </p>
                    </div>
                    <div className="w-px h-12 bg-border/50" />
                    <div className="text-right">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">目标达成率</p>
                        <p className={cn(
                            "text-2xl font-extrabold mono-number mt-0.5",
                            completion >= 100 ? "text-success text-shadow-glow-success drop-shadow-[0_0_8px_rgba(34,197,94,0.5)]" : "text-warning"
                        )}>
                            {completion}%
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex-1 min-h-[250px] relative z-10">
                <ChartContainer config={chartConfig} className="w-full h-full">
                    <ComposedChart data={revenueData} margin={{ top: 20, right: 0, left: -20, bottom: 0 }}>
                        <defs>
                            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={1} />
                                <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border)/0.5)" />
                        <XAxis 
                            dataKey="month" 
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12, fontWeight: 500 }}
                            tickLine={false}
                            axisLine={false}
                            dy={10}
                        />
                        <YAxis 
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12, fontWeight: 500 }}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(value) => `${value}w`}
                            dx={-10}
                        />
                        <Tooltip 
                            content={<ChartTooltipContent />}
                            formatter={(value: number, name: string) => [
                                `¥${value}万`, 
                                name === 'revenue' ? '实际营收' : '目标'
                            ]}
                            cursor={{ fill: 'hsl(var(--primary)/0.05)' }}
                        />
                        {monthlyRevenueTarget > 0 && (
                            <ReferenceLine 
                                y={monthlyRevenueTarget} 
                                stroke="hsl(var(--warning)/0.8)" 
                                strokeDasharray="5 5"
                                strokeWidth={2}
                            />
                        )}
                        <Bar 
                            dataKey="revenue" 
                            fill="url(#barGradient)" 
                            radius={[6, 6, 0, 0]}
                            barSize={32}
                            animationDuration={1500}
                        />
                        <Line 
                            type="monotone" 
                            dataKey="target" 
                            stroke="hsl(var(--warning))" 
                            strokeWidth={3}
                            strokeDasharray="5 5"
                            dot={{ fill: "hsl(var(--warning))", strokeWidth: 2, r: 4 }}
                            activeDot={{ r: 6, strokeWidth: 0 }}
                            animationDuration={1500}
                        />
                    </ComposedChart>
                </ChartContainer>
            </div>

            <div className="flex items-center justify-center gap-8 mt-6 relative z-10">
                <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-background/30 border border-border/30">
                    <div className="w-4 h-4 rounded-sm bg-gradient-to-b from-primary to-primary/40 shadow-[0_0_8px_rgba(59,130,246,0.3)]" />
                    <span className="text-xs font-semibold text-foreground tracking-wide">实际营收</span>
                </div>
                <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-background/30 border border-border/30">
                    <div className="w-5 h-0.5 bg-warning shadow-[0_0_8px_rgba(234,179,8,0.5)]" />
                    <span className="text-xs font-semibold text-foreground tracking-wide">预期目标</span>
                </div>
            </div>
        </div>
    );
}
