import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';
import { ChartContainer, ChartTooltipContent } from '@/components/ui/chart';
import { useTeamPerformance } from '@/hooks/useSalesData';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// Fallback mock data
const mockTeamData = [
  { name: '王晓明', score: 95, bonus: 8200, calls: 156, conversions: 12 },
  { name: '刘芳', score: 91, bonus: 6800, calls: 142, conversions: 10 },
  { name: '张明', score: 87, bonus: 4850, calls: 128, conversions: 8 },
  { name: '陈伟', score: 82, bonus: 3600, calls: 115, conversions: 6 },
  { name: '李娜', score: 78, bonus: 2900, calls: 98, conversions: 5 },
];

const chartConfig = {
  score: {
    label: "绩效分",
    color: "hsl(var(--primary))",
  },
};

const getBarColor = (score: number) => {
  if (score >= 90) return 'hsl(var(--success))';
  if (score >= 80) return 'hsl(var(--primary))';
  if (score >= 70) return 'hsl(var(--warning))';
  return 'hsl(var(--destructive))';
};

export function TeamPerformanceChart() {
  const { data: rawData, isLoading } = useTeamPerformance();

  const teamData = React.useMemo(() => {
    if (!Array.isArray(rawData) || rawData.length === 0) return mockTeamData;
    return rawData.slice(0, 5); // Top 5 performers
  }, [rawData]);

  const avgScore = Math.round(teamData.reduce((sum, m) => sum + m.score, 0) / teamData.length);
  const hasRealData = Array.isArray(rawData) && rawData.length > 0;

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
        <div className="relative overflow-hidden card-glass rounded-3xl p-6 sm:p-8 border border-border/50 shadow-2xl transition-all duration-300 h-full flex flex-col group">
            <div className="absolute -bottom-20 -left-20 w-64 h-64 bg-primary/10 blur-[80px] rounded-full pointer-events-none group-hover:bg-primary/20 transition-colors duration-700" />
            
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8 relative z-10">
                <div>
                    <h3 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/80">
                        AI 团队战力雷达
                    </h3>
                    <p className="text-sm font-medium text-muted-foreground mt-1 flex items-center gap-2">
                        核心成员绩效分综合分析
                        {!hasRealData && <span className="text-warning px-2 py-0.5 rounded-md bg-warning/10 text-xs border border-warning/20">AI 模拟推演模式</span>}
                    </p>
                </div>
                <div className="flex items-center gap-4 text-sm bg-background/40 backdrop-blur-md px-4 py-2 rounded-xl border border-border/50 shadow-inner">
                    <span className="text-muted-foreground font-semibold">团队战力均值</span>
                    <span className="text-xl font-extrabold text-primary mono-number text-shadow-glow drop-shadow-[0_0_8px_rgba(59,130,246,0.3)]">{avgScore}</span>
                </div>
            </div>

            <div className="flex-1 min-h-[250px] relative z-10">
                <ChartContainer config={chartConfig} className="w-full h-full">
                    <BarChart data={teamData} layout="vertical" margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-border/50" horizontal={false} />
                        <XAxis 
                            type="number"
                            domain={[0, 100]}
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12, fontWeight: 500 }}
                            tickLine={false}
                            axisLine={false}
                            dx={10}
                        />
                        <YAxis 
                            dataKey="name" 
                            type="category"
                            width={70}
                            tick={{ fill: 'hsl(var(--foreground))', fontSize: 13, fontWeight: 600 }}
                            tickLine={false}
                            axisLine={false}
                            dy={4}
                        />
                        <Tooltip 
                            content={<ChartTooltipContent />}
                            formatter={(value: number, name: string, props: { payload: { bonus: number; calls: number; conversions: number } }) => [
                                <div key="tooltip" className="space-y-1.5 min-w-[120px]">
                                    <div className="flex items-center justify-between font-bold text-sm">
                                        <span>综合战力</span>
                                        <span className={cn(
                                            value >= 90 ? "text-success" : value >= 80 ? "text-primary" : value >= 70 ? "text-warning" : "text-destructive"
                                        )}>{value}</span>
                                    </div>
                                    <div className="h-px w-full bg-border/50 my-1"/>
                                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                                        <span>预测奖金</span>
                                        <span className="font-semibold text-foreground">¥{props.payload.bonus.toLocaleString()}</span>
                                    </div>
                                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                                        <span>有效通话</span>
                                        <span className="font-semibold text-foreground">{props.payload.calls}次</span>
                                    </div>
                                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                                        <span>成单转化</span>
                                        <span className="font-semibold text-foreground">{props.payload.conversions}单</span>
                                    </div>
                                </div>,
                                ''
                            ]}
                            cursor={{ fill: 'hsl(var(--primary)/0.05)', radius: 4 }}
                        />
                        <Bar 
                            dataKey="score" 
                            radius={[0, 6, 6, 0]}
                            barSize={20}
                            animationDuration={1500}
                        >
                            {teamData.map((entry, index) => (
                                <Cell 
                                    key={`cell-${index}`} 
                                    fill={getBarColor(entry.score)} 
                                    className="transition-all duration-300 hover:opacity-80 drop-shadow-md"
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ChartContainer>
            </div>

            <div className="flex items-center justify-center gap-6 mt-6 relative z-10 p-3 bg-background/30 backdrop-blur-md rounded-2xl border border-border/50 flex-wrap">
                <div className="flex items-center gap-2">
                    <div className="w-3.5 h-3.5 rounded-sm bg-gradient-success glow-success" />
                    <span className="text-xs font-semibold text-foreground">S级战略专家 (≥90)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3.5 h-3.5 rounded-sm bg-gradient-primary shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
                    <span className="text-xs font-semibold text-foreground">A级核心骨干 (80-89)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3.5 h-3.5 rounded-sm bg-gradient-warning shadow-[0_0_8px_rgba(234,179,8,0.5)]" />
                    <span className="text-xs font-semibold text-foreground">B级中坚力量 (70-79)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3.5 h-3.5 rounded-sm bg-destructive shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
                    <span className="text-xs font-semibold text-foreground">C级潜力新星 (&lt;70)</span>
                </div>
            </div>
        </div>
    );
}
