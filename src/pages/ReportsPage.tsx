/**
 * 数据分析报表页面
 * 多 Tab（销售/审批/绩效/使用）+ 时间范围选择 + 导出 + 图表
 */

import React, { useState, useMemo } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { LoadingState } from '@/components/common/LoadingState';
import { ChartCard } from '@/components/common/ChartCard';
import { iconColors, iconBackgrounds, typography } from '@/lib/design-tokens';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  FileDown,
  DollarSign,
  CheckCircle2,
  Users,
  MessageSquare,
  Zap,
  Clock,
  Target,
  Activity,
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { useSalesReport, useApprovalReport, usePerformanceReport, useUsageReport } from '@/hooks/useReports';
import { toast } from 'sonner';
import { chartColors, CHART_COLORS } from '@/lib/chartColors';

// 时间范围预设
const TIME_PRESETS = [
  { value: 'today', label: '今日' },
  { value: 'week', label: '本周' },
  { value: 'month', label: '本月' },
  { value: 'quarter', label: '本季度' },
];

// 图表颜色
const COLORS = [...CHART_COLORS.slice(0, 4), chartColors.success, chartColors.warning];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  color = 'text-blue-500',
  bgColor = 'bg-blue-500/10',
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'stable';
  color?: string;
  bgColor?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
          <div className={`p-3 rounded-full ${bgColor}`}>
            <Icon className={`w-6 h-6 ${color}`} />
          </div>
        </div>
        {trend && (
          <div className="mt-2 flex items-center text-xs">
            {trend === 'up' && <TrendingUp className="w-3 h-3 text-green-500 mr-1" />}
            {trend === 'down' && <TrendingDown className="w-3 h-3 text-red-500 mr-1" />}
            <span className={trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-muted-foreground'}>
              {trend === 'up' ? '上升趋势' : trend === 'down' ? '下降趋势' : '持平'}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ────────────────── Sales Tab ────────────────── */
function SalesTab({ dateRange }: { dateRange: { preset: string } }) {
  const { data, isLoading } = useSalesReport(dateRange, 'day');
  const report = data as AnyData | undefined;

  if (isLoading) return <ReportSkeleton />;

  const summary = report?.summary || {};
  const chartData = (report?.data || []) as AnyData[];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="总销售额" value={`\u00A5${Number(summary.total_revenue || 0).toLocaleString()}`} icon={DollarSign} trend="up" color="text-green-500" bgColor="bg-green-500/10" />
        <StatCard title="成交数" value={summary.total_conversions || 0} icon={CheckCircle2} trend="up" color="text-blue-500" bgColor="bg-blue-500/10" />
        <StatCard title="线索数" value={summary.total_leads || 0} icon={Users} color="text-purple-500" bgColor="bg-purple-500/10" />
        <StatCard title="转化率" value={`${summary.overall_conversion_rate || 0}%`} icon={Target} trend="stable" color="text-orange-500" bgColor="bg-orange-500/10" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">销售趋势</CardTitle>
            <CardDescription>销售额与成交数走势</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData.slice(-14)}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="revenue" name="销售额" stroke={chartColors.success} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="conversions" name="成交数" stroke={chartColors.info} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">每日转化率</CardTitle>
            <CardDescription>线索到成交转化趋势</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData.slice(-14)}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="conversion_rate" name="转化率%" fill={chartColors.warning} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ────────────────── Approvals Tab ────────────────── */
function ApprovalsTab({ dateRange }: { dateRange: { preset: string } }) {
  const { data, isLoading } = useApprovalReport(dateRange);
  const report = data as AnyData | undefined;

  if (isLoading) return <ReportSkeleton />;

  const summary = report?.summary || {};
  const byType = report?.by_type || {};

  const pieData = Object.entries(byType).map(([key, value]) => ({
    name: key === 'expense' ? '报销' : key === 'leave' ? '请假' : key === 'purchase' ? '采购' : key === 'travel' ? '差旅' : key,
    value: value as number,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="总审批数" value={summary.total || 0} icon={BarChart3} color="text-blue-500" bgColor="bg-blue-500/10" />
        <StatCard title="平均处理时间" value={`${summary.avg_processing_hours || 0}h`} icon={Clock} color="text-orange-500" bgColor="bg-orange-500/10" />
        <StatCard title="自动审批率" value={`${summary.auto_approval_rate || 0}%`} icon={Zap} trend="up" color="text-green-500" bgColor="bg-green-500/10" />
        <StatCard title="驳回率" value={`${summary.rejection_rate || 0}%`} icon={TrendingDown} color="text-red-500" bgColor="bg-red-500/10" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">审批状态分布</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={[
                    { name: '已通过', value: summary.approved || 0 },
                    { name: '已驳回', value: summary.rejected || 0 },
                    { name: '待审批', value: summary.pending || 0 },
                  ]}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  dataKey="value"
                >
                  {[chartColors.success, chartColors.danger, chartColors.warning].map((color, index) => (
                    <Cell key={index} fill={color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">按类型分布</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={pieData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 12 }} width={60} />
                <Tooltip />
                <Bar dataKey="value" name="数量" fill={chartColors.info} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ────────────────── Performance Tab ────────────────── */
function PerformanceTab({ dateRange }: { dateRange: { preset: string } }) {
  const { data, isLoading } = usePerformanceReport(dateRange);
  const report = data as AnyData | undefined;

  if (isLoading) return <ReportSkeleton />;

  const summary = report?.summary || {};
  const rankings = (report?.rankings || []) as AnyData[];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="团队总积分" value={Number(summary.team_total_score || 0).toLocaleString()} icon={Activity} color="text-blue-500" bgColor="bg-blue-500/10" />
        <StatCard title="平均绩效" value={summary.team_avg_score || 0} icon={Target} trend="up" color="text-green-500" bgColor="bg-green-500/10" />
        <StatCard title="团队成员" value={summary.member_count || 0} icon={Users} color="text-purple-500" bgColor="bg-purple-500/10" />
        <StatCard title="最佳员工" value={summary.top_performer || 'N/A'} icon={TrendingUp} color="text-orange-500" bgColor="bg-orange-500/10" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">绩效排名</CardTitle>
          <CardDescription>团队成员绩效得分与目标完成率</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={rankings.slice(0, 10)}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="score" name="绩效分" fill={chartColors.info} radius={[4, 4, 0, 0]} />
              <Bar dataKey="completion_rate" name="完成率%" fill={chartColors.success} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

/* ────────────────── Usage Tab ────────────────── */
function UsageTab({ dateRange }: { dateRange: { preset: string } }) {
  const { data, isLoading } = useUsageReport(dateRange);
  const report = data as AnyData | undefined;

  if (isLoading) return <ReportSkeleton />;

  const summary = report?.summary || {};
  const modelDist = report?.model_distribution || {};
  const featureUsage = (report?.feature_usage || []) as AnyData[];

  const modelData = Object.entries(modelDist).map(([name, count]) => ({
    name,
    value: count as number,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="对话总量" value={Number(summary.total_conversations || 0).toLocaleString()} icon={MessageSquare} trend="up" color="text-blue-500" bgColor="bg-blue-500/10" />
        <StatCard title="Token 消耗" value={Number(summary.total_tokens || 0).toLocaleString()} icon={Zap} color="text-orange-500" bgColor="bg-orange-500/10" />
        <StatCard title="平均 Token/对话" value={summary.avg_tokens_per_chat || 0} icon={BarChart3} color="text-purple-500" bgColor="bg-purple-500/10" />
        <StatCard title="活跃用户" value={summary.active_users || 0} icon={Users} color="text-green-500" bgColor="bg-green-500/10" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">模型使用分布</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={modelData}
                  cx="50%"
                  cy="50%"
                  labelLine
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  dataKey="value"
                >
                  {modelData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">功能使用频率</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={featureUsage} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="feature" type="category" tick={{ fontSize: 12 }} width={80} />
                <Tooltip />
                <Bar dataKey="count" name="使用次数" fill="hsl(var(--primary) / 0.7)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ────────────────── Skeleton ────────────────── */
function ReportSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <Card key={i}><CardContent className="pt-6"><Skeleton className="h-16 w-full" /></CardContent></Card>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        <Card><CardContent className="pt-6"><Skeleton className="h-[300px] w-full" /></CardContent></Card>
        <Card><CardContent className="pt-6"><Skeleton className="h-[300px] w-full" /></CardContent></Card>
      </div>
    </div>
  );
}

/* ────────────────── Main Page ────────────────── */
function ReportsPage() {
  const [activeTab, setActiveTab] = useState('sales');
  const [timePreset, setTimePreset] = useState('month');

  const dateRange = useMemo(() => ({ preset: timePreset }), [timePreset]);

  const handleExport = () => {
    toast.success('正在生成报表导出文件...');

    // Collect visible data from the active tab and export as CSV
    try {
      const headers = ['指标', '数值'];
      const rows: string[][] = [];

      // Get stats from the page elements
      const statElements = document.querySelectorAll('[data-export]');
      statElements.forEach(el => {
        const label = el.getAttribute('data-export-label') || '';
        const value = el.textContent || '';
        if (label) rows.push([label, value]);
      });

      // If no data-export elements, fallback to a simple summary
      if (rows.length === 0) {
        rows.push(['报表类型', activeTab]);
        rows.push(['时间范围', timePreset]);
        rows.push(['导出时间', new Date().toLocaleString('zh-CN')]);
      }

      const csvContent = [headers, ...rows]
        .map(row => row.map(cell => `"${cell}"`).join(','))
        .join('\n');

      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `报表_${activeTab}_${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(url);

      toast.success('报表导出完成');
    } catch {
      toast.error('导出失败，请稍后重试');
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">数据分析报表</h1>
          <p className="text-muted-foreground">全面的业务数据分析与可视化</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={timePreset} onValueChange={setTimePreset}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIME_PRESETS.map(p => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={handleExport} className="gap-2">
            <FileDown className="w-4 h-4" />
            导出
          </Button>
        </div>
      </div>

      {/* 标签页 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="sales" className="gap-2">
            <DollarSign className="w-4 h-4 hidden sm:block" />
            销售
          </TabsTrigger>
          <TabsTrigger value="approvals" className="gap-2">
            <CheckCircle2 className="w-4 h-4 hidden sm:block" />
            审批
          </TabsTrigger>
          <TabsTrigger value="performance" className="gap-2">
            <Target className="w-4 h-4 hidden sm:block" />
            绩效
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-2">
            <MessageSquare className="w-4 h-4 hidden sm:block" />
            使用
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sales"><SalesTab dateRange={dateRange} /></TabsContent>
        <TabsContent value="approvals"><ApprovalsTab dateRange={dateRange} /></TabsContent>
        <TabsContent value="performance"><PerformanceTab dateRange={dateRange} /></TabsContent>
        <TabsContent value="usage"><UsageTab dateRange={dateRange} /></TabsContent>
      </Tabs>
    </div>
  );
}

export default ReportsPage;
