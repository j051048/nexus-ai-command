/**
 * VMD 数据看板
 * 统计卡片(含趋势箭头) + 任务完成趋势 + 场景分布 + Agent负荷 + 模型用量 + 合规趋势
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
  ListTodo,
  Bot,
  Target,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  useVMDStats,
  useVMDTaskTrend,
  useVMDSceneDistribution,
  useVMDAgentWorkload,
  useModelUsageStats,
  useVMDComplianceTrend,
} from '@/hooks/useVMD';
import { chartColors } from '@/lib/chartColors';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRecord = Record<string, any>;

// 饼图配色
const PIE_COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'];

const SCENE_NAMES: Record<string, string> = {
  new_product_launch: '新品上市',
  bid_support: '招投标',
  exhibition: '展会运营',
  content_marketing: '内容营销',
  rnd_synergy: '研产销协同',
  after_sales: '售后运营',
};

const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'hsl(var(--card))',
    border: '1px solid hsl(var(--border))',
    borderRadius: 8,
    fontSize: 12,
  },
  labelStyle: { color: 'hsl(var(--foreground))' },
};

export default function VMDDashboard() {
  const [trendDays, setTrendDays] = useState(30);

  // Queries
  const { data: stats, isLoading: statsLoading } = useVMDStats();
  const { data: taskTrend } = useVMDTaskTrend(trendDays);
  const { data: sceneDist } = useVMDSceneDistribution();
  const { data: agentWorkload } = useVMDAgentWorkload();
  const { data: modelUsage } = useModelUsageStats('week');
  const { data: complianceTrend } = useVMDComplianceTrend(trendDays);

  // Stat cards config
  const statCards = [
    {
      label: '今日任务数',
      value: stats?.today_tasks ?? 0,
      trend: stats?.today_tasks_trend ?? 0,
      icon: ListTodo,
      color: 'text-blue-500',
      bg: 'bg-blue-500/10',
    },
    {
      label: '活跃Agent数',
      value: stats?.active_agents ?? 0,
      trend: stats?.active_agents_trend ?? 0,
      icon: Bot,
      color: 'text-green-500',
      bg: 'bg-green-500/10',
    },
    {
      label: '新增线索',
      value: stats?.new_clues ?? 0,
      trend: stats?.new_clues_trend ?? 0,
      icon: Target,
      color: 'text-amber-500',
      bg: 'bg-amber-500/10',
    },
    {
      label: '合规校验数',
      value: stats?.compliance_checks ?? stats?.pending_review ?? 0,
      trend: stats?.compliance_checks_trend ?? 0,
      icon: ShieldCheck,
      color: 'text-purple-500',
      bg: 'bg-purple-500/10',
    },
  ];

  // Scene distribution with Chinese names
  const sceneDistNamed = (sceneDist || []).map((item: AnyRecord) => ({
    ...item,
    name: SCENE_NAMES[item.scene_code as string] || (item.scene_code as string),
  }));

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">数据看板</h1>
          <p className="text-muted-foreground">虚拟市场部运营数据概览与趋势分析</p>
        </div>
        <Select value={String(trendDays)} onValueChange={(v) => setTrendDays(Number(v))}>
          <SelectTrigger className="w-[130px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">近 7 天</SelectItem>
            <SelectItem value="14">近 14 天</SelectItem>
            <SelectItem value="30">近 30 天</SelectItem>
            <SelectItem value="90">近 90 天</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* ====== Row 1: Stat Cards with trend arrows ====== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}><CardContent className="pt-6"><Skeleton className="h-16 w-full" /></CardContent></Card>
          ))
        ) : (
          statCards.map((stat) => {
            const Icon = stat.icon;
            const isUp = stat.trend > 0;
            const isDown = stat.trend < 0;
            return (
              <Card key={stat.label}>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", stat.bg)}>
                      <Icon className={cn("w-5 h-5", stat.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-muted-foreground">{stat.label}</p>
                      <div className="flex items-center gap-2">
                        <p className="text-2xl font-bold">{stat.value}</p>
                        {stat.trend !== 0 && (
                          <span className={cn(
                            "flex items-center gap-0.5 text-xs font-medium",
                            isUp ? "text-green-600 dark:text-green-400" : "",
                            isDown ? "text-red-600 dark:text-red-400" : ""
                          )}>
                            {isUp && <TrendingUp className="w-3 h-3" />}
                            {isDown && <TrendingDown className="w-3 h-3" />}
                            {Math.abs(stat.trend)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>

      {/* ====== Row 2: Task Trend (line) + Scene Distribution (pie) ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">任务完成趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={taskTrend || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="created" name="新建" stroke={chartColors.info} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="completed" name="完成" stroke={chartColors.success} strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="failed" name="失败" stroke={chartColors.danger} strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">场景分布</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sceneDistNamed}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="count"
                    nameKey="name"
                    label={({ name, percent }: { name: string; percent: number }) =>
                      `${name} ${(percent * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {sceneDistNamed.map((_: AnyRecord, idx: number) => (
                      <Cell key={`cell-${idx}`} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip {...TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ====== Row 3: Agent Workload (bar) + Model Usage (bar) ====== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Agent 任务负荷</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agentWorkload || []} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis
                    type="category"
                    dataKey="agent_name"
                    tick={{ fontSize: 11 }}
                    stroke="hsl(var(--muted-foreground))"
                    width={80}
                  />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="executing" name="执行中" fill={chartColors.warning} stackId="a" />
                  <Bar dataKey="completed" name="已完成" fill={chartColors.success} stackId="a" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">模型调用量</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={modelUsage || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="model_code" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="total_tokens" name="Token 总量" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="call_count" name="调用次数" fill={chartColors.info} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ====== Row 4: Compliance Trend (area) ====== */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">合规校验趋势</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={complianceTrend || []}>
                <defs>
                  <linearGradient id="cleanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColors.success} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={chartColors.success} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="issueGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColors.danger} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={chartColors.danger} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area
                  type="monotone"
                  dataKey="clean"
                  name="合规通过"
                  stroke={chartColors.success}
                  fill="url(#cleanGrad)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="has_issues"
                  name="存在问题"
                  stroke={chartColors.danger}
                  fill="url(#issueGrad)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
