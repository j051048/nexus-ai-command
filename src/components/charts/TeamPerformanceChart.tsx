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

const teamData = [
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
  const avgScore = Math.round(teamData.reduce((sum, m) => sum + m.score, 0) / teamData.length);

  return (
    <div className="bg-card rounded-2xl p-4 sm:p-6 border border-border">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6">
        <div>
          <h3 className="text-lg font-semibold text-foreground">团队绩效对比</h3>
          <p className="text-sm text-muted-foreground">本周成员绩效分对比分析</p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div className="px-3 py-1.5 rounded-lg bg-secondary">
            <span className="text-muted-foreground">团队均分：</span>
            <span className="font-bold text-foreground ml-1 mono-number">{avgScore}</span>
          </div>
        </div>
      </div>

      <ChartContainer config={chartConfig} className="h-[200px] sm:h-[250px] w-full">
        <BarChart data={teamData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis 
            type="number"
            domain={[0, 100]}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis 
            dataKey="name" 
            type="category"
            width={60}
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip 
            content={<ChartTooltipContent />}
            formatter={(value: number, name: string, props: any) => [
              <div key="tooltip" className="space-y-1">
                <div>绩效分: {value}</div>
                <div>奖金: ¥{props.payload.bonus.toLocaleString()}</div>
                <div>通话: {props.payload.calls}次</div>
                <div>转化: {props.payload.conversions}单</div>
              </div>,
              ''
            ]}
          />
          <Bar 
            dataKey="score" 
            radius={[0, 4, 4, 0]}
            barSize={24}
          >
            {teamData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getBarColor(entry.score)} />
            ))}
          </Bar>
        </BarChart>
      </ChartContainer>

      <div className="flex items-center justify-center gap-4 mt-4 text-xs flex-wrap">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-success" />
          <span className="text-muted-foreground">≥90 优秀</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-primary" />
          <span className="text-muted-foreground">80-89 达标</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-warning" />
          <span className="text-muted-foreground">70-79 待提升</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-destructive" />
          <span className="text-muted-foreground">&lt;70 需关注</span>
        </div>
      </div>
    </div>
  );
}
