import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Coins, TrendingUp, TrendingDown, AlertTriangle, Activity, Zap, BarChart3 } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';

interface UsageSummary {
  tokens_used: number;
  cost_usd: number;
  requests: number;
  tokens_limit: number;
  cost_limit_usd: number;
}

interface HistoryItem {
  date: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

interface QuotaAlert {
  month_tokens: number;
  month_cost_usd: number;
  month_requests: number;
  monthly_token_budget: number;
  monthly_cost_budget_usd: number;
  usage_percentage: number;
  alert_level: 'normal' | 'warning' | 'critical' | 'exhausted';
  alert_message: string | null;
}

interface CostReport {
  by_department?: Record<string, { tokens: number; cost_usd: number; requests: number }>;
  by_project?: Record<string, { tokens: number; cost_usd: number; requests: number }>;
  total_tokens?: number;
  total_cost_usd?: number;
  period_days?: number;
}

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#ede9fe'];

const ALERT_CONFIG: Record<string, { color: string; label: string }> = {
  normal: { color: 'bg-green-500', label: '正常' },
  warning: { color: 'bg-amber-500', label: '预警' },
  critical: { color: 'bg-red-500', label: '紧急' },
  exhausted: { color: 'bg-red-700', label: '已耗尽' },
};

export default function LLMCostDashboard() {
  const [days, setDays] = useState('30');
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState<UsageSummary | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [quota, setQuota] = useState<QuotaAlert | null>(null);
  const [costReport, setCostReport] = useState<CostReport | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [currentRes, historyRes, quotaRes, costRes] = await Promise.all([
        aiClient.fetch<{ success?: boolean; data?: UsageSummary }>('/api/usage/current'),
        aiClient.fetch<{ success?: boolean; data?: { history?: HistoryItem[] } }>(`/api/usage/history?days=${days}`),
        aiClient.fetch<{ success?: boolean; data?: QuotaAlert }>('/api/usage/quota-alert'),
        aiClient.fetch<{ success?: boolean; data?: CostReport }>(`/api/usage/cost-report?days=${days}`),
      ]);

      if (currentRes?.success) setCurrent(currentRes.data ?? null);
      if (historyRes?.success) {
        const h = historyRes.data?.history || [];
        setHistory([...h].reverse());
      }
      if (quotaRes?.success) setQuota(quotaRes.data ?? null);
      if (costRes?.success) setCostReport(costRes.data ?? null);
    } catch {
      toast.error('加载用量数据失败');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatTokens = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return String(n);
  };

  const formatCost = (n: number) => `$${n.toFixed(4)}`;

  const deptData = costReport?.by_department
    ? Object.entries(costReport.by_department).map(([name, v]) => ({
        name: name || '未分配',
        tokens: v.tokens,
        cost: v.cost_usd,
        requests: v.requests,
      }))
    : [];

  const alertConfig = ALERT_CONFIG[quota?.alert_level || 'normal'];

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Coins className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">LLM 成本看板</h1>
            <p className="text-muted-foreground">Token 消耗、费用归因与配额监控</p>
          </div>
        </div>
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">最近 7 天</SelectItem>
            <SelectItem value="30">最近 30 天</SelectItem>
            <SelectItem value="90">最近 90 天</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
        </div>
      ) : (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5" /> 今日 Token
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatTokens(current?.tokens_used || 0)}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  限额 {formatTokens(current?.tokens_limit || 0)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5" /> 今日费用
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatCost(current?.cost_usd || 0)}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  限额 {formatCost(current?.cost_limit_usd || 0)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5" /> 本月 Token
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatTokens(quota?.month_tokens || 0)}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  预算 {formatTokens(quota?.monthly_token_budget || 0)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" /> 配额状态
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <p className="text-2xl font-bold">{quota?.usage_percentage?.toFixed(1) || 0}%</p>
                  <Badge variant="outline" className="text-xs">
                    <span className={`w-2 h-2 rounded-full mr-1.5 ${alertConfig.color}`} />
                    {alertConfig.label}
                  </Badge>
                </div>
                {quota?.alert_message && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">{quota.alert_message}</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Token Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" /> Token 用量趋势
                </CardTitle>
              </CardHeader>
              <CardContent>
                {history.length > 0 ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={history}>
                      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                      <YAxis tick={{ fontSize: 11 }} tickFormatter={formatTokens} />
                      <Tooltip
                        formatter={(v: number) => [formatTokens(v), 'Tokens']}
                        labelFormatter={(l) => `日期: ${l}`}
                      />
                      <Line type="monotone" dataKey="tokens" stroke="#6366f1" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[260px] flex items-center justify-center text-muted-foreground text-sm">
                    暂无历史数据
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Cost Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Coins className="w-4 h-4" /> 费用趋势
                </CardTitle>
              </CardHeader>
              <CardContent>
                {history.length > 0 ? (
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={history}>
                      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                      <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                      <Tooltip
                        formatter={(v: number) => [formatCost(v), '费用']}
                        labelFormatter={(l) => `日期: ${l}`}
                      />
                      <Bar dataKey="cost_usd" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[260px] flex items-center justify-center text-muted-foreground text-sm">
                    暂无历史数据
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Department Cost Attribution */}
          {deptData.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <BarChart3 className="w-4 h-4" /> 部门成本分布
                  </CardTitle>
                  <CardDescription>过去 {days} 天按部门统计</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie
                        data={deptData}
                        dataKey="cost"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={90}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      >
                        {deptData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => [formatCost(v), '费用']} />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">部门明细</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {deptData.map((dept, i) => (
                      <div key={dept.name} className="flex items-center justify-between p-3 rounded-lg bg-secondary/30">
                        <div className="flex items-center gap-3">
                          <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                          <span className="text-sm font-medium">{dept.name}</span>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold">{formatCost(dept.cost)}</p>
                          <p className="text-xs text-muted-foreground">{formatTokens(dept.tokens)} tokens / {dept.requests} 次</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
