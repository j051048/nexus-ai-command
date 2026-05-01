import { getApiBaseUrl } from "@/lib/apiConfig";
/**
 * Agent 调试面板
 * HITL Admin Debug Panel for inspecting agent execution traces.
 * Shows stats overview, trace list with status filtering, expandable step detail.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Bug,
  Activity,
  Clock,
  Zap,
  Coins,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  ArrowRight,
  Wrench,
  ThumbsUp,
  ThumbsDown,
  TrendingUp,
  SmilePlus,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { cn } from '@/lib/utils';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';

// ─── Types ──────────────────────────────────────────────

interface TraceStats {
  total_traces: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_duration_ms: number;
  success_rate: number;
  by_status: Record<string, number>;
}

interface TraceListItem {
  trace_id: string;
  thread_id: string;
  user_id: string;
  query: string;
  status: string;
  start_time: string;
  total_duration_ms: number | null;
  total_tokens: number;
  total_cost_usd: number;
  step_count: number;
  tags: string[];
}

interface TraceStep {
  step_id: string;
  node_type: string;
  timestamp: number;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  duration_ms: number | null;
  status: string;
  error: string | null;
  tokens_used: number;
  tool_calls: Record<string, unknown>[];
}

interface TraceDetail {
  trace_id: string;
  thread_id: string;
  user_id: string;
  query: string;
  status: string;
  start_time: number;
  end_time: number | null;
  total_duration_ms: number | null;
  total_tokens: number;
  total_cost_usd: number;
  steps: TraceStep[];
  final_response: string | null;
  metadata: Record<string, unknown>;
  tags: string[];
}

interface QualitySummary {
  total_traces: number;
  success_rate: number;
  avg_duration_ms: number;
  total_tokens: number;
  total_cost_usd: number;
  satisfaction_rate: number;
  positive_feedback: number;
  negative_feedback: number;
  days: number;
}

interface QualityTrendItem {
  metric_date: string;
  total_traces: number;
  completed_traces: number;
  failed_traces: number;
  positive_feedback: number;
  negative_feedback: number;
  avg_duration_ms: number;
  total_tokens: number;
}

// ─── API Helper ──────────────────────────────────────────

const API_BASE_URL = getApiBaseUrl();

async function apiFetch<T>(endpoint: string): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  let url = API_BASE_URL;
  if (!url.startsWith('http')) {
    url = url.includes('localhost') ? `http://${url}` : `https://${url}`;
  }
  const cleanBase = url.replace(/\/$/, '');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  const fullUrl = `${cleanBase}/${cleanEndpoint}`;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const resp = await fetch(fullUrl, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  const json = await resp.json();
  if (json.success === false) throw new Error(json.error?.message || 'Unknown error');
  return json.data as T;
}

async function apiPost<T>(endpoint: string, body: Record<string, unknown>): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  let url = API_BASE_URL;
  if (!url.startsWith('http')) {
    url = url.includes('localhost') ? `http://${url}` : `https://${url}`;
  }
  const cleanBase = url.replace(/\/$/, '');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  const fullUrl = `${cleanBase}/${cleanEndpoint}`;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const resp = await fetch(fullUrl, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  const json = await resp.json();
  if (json.success === false) throw new Error(json.error?.message || 'Unknown error');
  return json.data as T;
}

// ─── Status Config ──────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  running: {
    label: '运行中',
    color: 'text-blue-600',
    bg: 'bg-blue-500/10',
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  },
  completed: {
    label: '已完成',
    color: 'text-green-600',
    bg: 'bg-green-500/10',
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  failed: {
    label: '失败',
    color: 'text-red-600',
    bg: 'bg-red-500/10',
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
  timeout: {
    label: '超时',
    color: 'text-yellow-600',
    bg: 'bg-yellow-500/10',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
  },
  cancelled: {
    label: '取消',
    color: 'text-gray-500',
    bg: 'bg-gray-500/10',
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
};

const NODE_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  router: { label: 'Router', color: 'bg-blue-500' },
  plan: { label: 'Plan', color: 'bg-purple-500' },
  execute: { label: 'Execute', color: 'bg-amber-500' },
  reflect: { label: 'Reflect', color: 'bg-cyan-500' },
  respond: { label: 'Respond', color: 'bg-green-500' },
  error: { label: 'Error', color: 'bg-red-500' },
};

// ─── Stat Card ──────────────────────────────────────────

function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className={`p-3 rounded-lg ${color}`}>{icon}</div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Step Timeline ──────────────────────────────────────

function StepTimeline({ steps }: { steps: TraceStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">暂无执行步骤</p>;
  }

  return (
    <div className="space-y-0 pl-2 py-2">
      {steps.map((step, idx) => {
        const nodeConfig = NODE_TYPE_LABELS[step.node_type] || { label: step.node_type, color: 'bg-gray-500' };
        const isLast = idx === steps.length - 1;
        return (
          <div key={step.step_id} className="relative pl-8 pb-4 group">
            {/* Timeline dot */}
            <div
              className={cn(
                'absolute left-0 top-1 w-6 h-6 rounded-full flex items-center justify-center ring-2 ring-background text-white text-[10px] font-bold',
                nodeConfig.color
              )}
            >
              {idx + 1}
            </div>
            {/* Connecting line */}
            {!isLast && (
              <div className="absolute left-[11px] top-7 bottom-0 w-px bg-border" />
            )}

            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline" className="text-xs font-mono">
                  {nodeConfig.label}
                </Badge>
                {step.status === 'completed' && (
                  <Badge variant="secondary" className="text-xs text-green-600 bg-green-500/10">
                    完成
                  </Badge>
                )}
                {step.status === 'failed' && (
                  <Badge variant="secondary" className="text-xs text-red-600 bg-red-500/10">
                    失败
                  </Badge>
                )}
                {step.duration_ms != null && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {step.duration_ms}ms
                  </span>
                )}
                {step.tokens_used > 0 && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Zap className="w-3 h-3" />
                    {step.tokens_used} tokens
                  </span>
                )}
              </div>

              {/* Tool calls */}
              {step.tool_calls.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Wrench className="w-3 h-3 text-muted-foreground" />
                  {step.tool_calls.map((tc, i) => (
                    <Badge key={i} variant="outline" className="text-[10px] font-mono">
                      {(tc as Record<string, string>).name || (tc as Record<string, string>).tool || `tool-${i + 1}`}
                    </Badge>
                  ))}
                </div>
              )}

              {/* Error message */}
              {step.error && (
                <div className="text-xs text-red-600 bg-red-500/10 rounded p-2 font-mono">
                  {step.error}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Flow Visualization ──────────────────────────────────

function FlowVisualization({ steps }: { steps: TraceStep[] }) {
  if (steps.length === 0) return null;

  const nodeTypes = steps.map((s) => s.node_type);

  return (
    <div className="flex items-center gap-1 flex-wrap py-2">
      {nodeTypes.map((nt, idx) => {
        const config = NODE_TYPE_LABELS[nt] || { label: nt, color: 'bg-gray-500' };
        return (
          <React.Fragment key={idx}>
            <span
              className={cn(
                'px-2 py-0.5 rounded text-[10px] font-bold text-white',
                config.color
              )}
            >
              {config.label}
            </span>
            {idx < nodeTypes.length - 1 && (
              <ArrowRight className="w-3 h-3 text-muted-foreground" />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────

function AgentDebugPanel() {
  const [stats, setStats] = useState<TraceStats | null>(null);
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<TraceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [qualitySummary, setQualitySummary] = useState<QualitySummary | null>(null);
  const [qualityTrend, setQualityTrend] = useState<QualityTrendItem[]>([]);

  // Fetch stats and list
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, listData] = await Promise.all([
        apiFetch<TraceStats>('/api/v1/admin/traces/stats'),
        apiFetch<{ traces: TraceListItem[]; total: number }>(
          `/api/v1/admin/traces/list?limit=100${statusFilter !== 'all' ? `&status=${statusFilter}` : ''}`
        ),
      ]);
      setStats(statsData);
      setTraces(listData.traces);
    } catch (err) {
      console.error('Failed to fetch trace data:', err);
      toast.error('获取Agent调试数据失败');
    } finally {
      setLoading(false);
    }

    // Fetch quality data separately (non-blocking)
    try {
      const [summaryData, trendData] = await Promise.all([
        apiFetch<QualitySummary>('/api/v1/admin/traces/quality/summary?days=7'),
        apiFetch<{ trend: QualityTrendItem[]; days: number }>('/api/v1/admin/traces/quality/trend?days=30'),
      ]);
      setQualitySummary(summaryData);
      setQualityTrend(trendData.trend || []);
    } catch (err) {
      console.error('Failed to fetch quality data:', err);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch detail when expanding a trace
  const handleToggleDetail = useCallback(async (traceId: string) => {
    if (expandedTraceId === traceId) {
      setExpandedTraceId(null);
      setTraceDetail(null);
      return;
    }

    setExpandedTraceId(traceId);
    setDetailLoading(true);
    try {
      const data = await apiFetch<{ trace: TraceDetail }>(
        `/api/v1/admin/traces/detail/${traceId}`
      );
      setTraceDetail(data.trace);
    } catch (err) {
      console.error('Failed to fetch trace detail:', err);
      toast.error('获取Trace详情失败');
    } finally {
      setDetailLoading(false);
    }
  }, [expandedTraceId]);

  // Format helpers
  const formatDuration = (ms: number | null) => {
    if (ms == null) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Bug className="w-7 h-7 text-primary" />
            Agent 调试面板
          </h1>
          <p className="text-sm text-muted-foreground">
            检视Agent执行轨迹，排查问题，优化性能
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[130px]">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="running">运行中</SelectItem>
              <SelectItem value="completed">已完成</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
              <SelectItem value="timeout">超时</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
            <RefreshCw className={cn("w-4 h-4 mr-1", loading && "animate-spin")} />
            刷新
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-16 w-full" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <StatCard
              title="总执行数"
              value={stats?.total_traces ?? 0}
              icon={<Activity className="w-5 h-5 text-blue-600" />}
              color="bg-blue-500/10"
            />
            <StatCard
              title="成功率"
              value={stats?.success_rate != null ? `${(stats.success_rate * 100).toFixed(1)}%` : '-'}
              icon={<CheckCircle2 className="w-5 h-5 text-green-600" />}
              color="bg-green-500/10"
            />
            <StatCard
              title="平均耗时"
              value={formatDuration(stats?.avg_duration_ms ?? null)}
              icon={<Clock className="w-5 h-5 text-amber-600" />}
              color="bg-amber-500/10"
            />
            <StatCard
              title="总Token消耗"
              value={stats?.total_tokens?.toLocaleString() ?? '0'}
              icon={<Coins className="w-5 h-5 text-purple-600" />}
              color="bg-purple-500/10"
            />
          </>
        )}
      </div>

      {/* Quality Summary Cards */}
      {qualitySummary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title={`成功率 (${qualitySummary.days}天)`}
            value={`${qualitySummary.success_rate}%`}
            icon={<TrendingUp className="w-5 h-5 text-emerald-600" />}
            color="bg-emerald-500/10"
          />
          <StatCard
            title="满意度"
            value={`${qualitySummary.satisfaction_rate}%`}
            icon={<SmilePlus className="w-5 h-5 text-pink-600" />}
            color="bg-pink-500/10"
          />
          <StatCard
            title="正面反馈"
            value={qualitySummary.positive_feedback}
            icon={<ThumbsUp className="w-5 h-5 text-green-600" />}
            color="bg-green-500/10"
          />
          <StatCard
            title="负面反馈"
            value={qualitySummary.negative_feedback}
            icon={<ThumbsDown className="w-5 h-5 text-red-600" />}
            color="bg-red-500/10"
          />
        </div>
      )}

      {/* Quality Trend Chart */}
      {qualityTrend.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              质量趋势 (最近30天)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={qualityTrend.map((d) => ({
                    ...d,
                    date: d.metric_date.slice(5),
                    success_rate:
                      d.total_traces > 0
                        ? Math.round((d.completed_traces / d.total_traces) * 1000) / 10
                        : 0,
                    satisfaction:
                      d.positive_feedback + d.negative_feedback > 0
                        ? Math.round(
                            (d.positive_feedback / (d.positive_feedback + d.negative_feedback)) * 1000
                          ) / 10
                        : 0,
                  }))}
                  margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" className="text-xs" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="left" className="text-xs" tick={{ fontSize: 11 }} />
                  <YAxis yAxisId="right" orientation="right" domain={[0, 100]} className="text-xs" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="total_traces"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    name="执行数"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="success_rate"
                    stroke="#22c55e"
                    strokeWidth={2}
                    dot={false}
                    name="成功率%"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="satisfaction"
                    stroke="#ec4899"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="满意度%"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Trace List Table */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" />
              执行记录
            </CardTitle>
            <Badge variant="secondary" className="text-xs">
              {traces.length} 条
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <RefreshCw className="w-5 h-5 animate-spin mr-2" />
              加载中...
            </div>
          ) : traces.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Bug className="w-10 h-10 mb-3 opacity-40" />
              <p>暂无Agent执行记录</p>
              <p className="text-xs mt-1">Agent执行后数据将自动出现在此处</p>
            </div>
          ) : (
            <ScrollArea className="max-h-[600px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[60px]"></TableHead>
                    <TableHead>Query</TableHead>
                    <TableHead className="w-[90px]">状态</TableHead>
                    <TableHead className="w-[80px]">耗时</TableHead>
                    <TableHead className="w-[80px]">Tokens</TableHead>
                    <TableHead className="w-[60px]">步骤</TableHead>
                    <TableHead className="w-[130px]">时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {traces.map((trace) => {
                    const statusCfg = STATUS_CONFIG[trace.status] || STATUS_CONFIG.completed;
                    const isExpanded = expandedTraceId === trace.trace_id;

                    return (
                      <React.Fragment key={trace.trace_id}>
                        <TableRow
                          className="cursor-pointer"
                          onClick={() => handleToggleDetail(trace.trace_id)}
                        >
                          <TableCell>
                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-muted-foreground" />
                            )}
                          </TableCell>
                          <TableCell>
                            <span className="text-sm line-clamp-1" title={trace.query}>
                              {trace.query || '(empty)'}
                            </span>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={cn('text-xs gap-1', statusCfg.color, statusCfg.bg)}
                            >
                              {statusCfg.icon}
                              {statusCfg.label}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm font-mono">
                            {formatDuration(trace.total_duration_ms)}
                          </TableCell>
                          <TableCell className="text-sm font-mono">
                            {trace.total_tokens.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-sm text-center">
                            {trace.step_count}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {formatTime(trace.start_time)}
                          </TableCell>
                        </TableRow>

                        {/* Expanded detail row */}
                        {isExpanded && (
                          <TableRow>
                            <TableCell colSpan={7} className="bg-muted/30 p-0">
                              <div className="p-4 space-y-4">
                                {detailLoading ? (
                                  <div className="flex items-center gap-2 py-4 text-muted-foreground">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    加载详情...
                                  </div>
                                ) : traceDetail ? (
                                  <>
                                    {/* Meta info */}
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                      <div>
                                        <span className="text-muted-foreground">Trace ID: </span>
                                        <span className="font-mono text-xs">{traceDetail.trace_id}</span>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">Thread ID: </span>
                                        <span className="font-mono text-xs">{traceDetail.thread_id}</span>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">费用: </span>
                                        <span className="font-mono">${traceDetail.total_cost_usd.toFixed(4)}</span>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">标签: </span>
                                        {traceDetail.tags.length > 0
                                          ? traceDetail.tags.map((t) => (
                                              <Badge key={t} variant="outline" className="text-[10px] mr-1">
                                                {t}
                                              </Badge>
                                            ))
                                          : <span className="text-xs text-muted-foreground">无</span>}
                                      </div>
                                    </div>

                                    {/* Flow visualization */}
                                    <div>
                                      <p className="text-xs font-medium text-muted-foreground mb-1">执行流程</p>
                                      <FlowVisualization steps={traceDetail.steps} />
                                    </div>

                                    {/* Step timeline */}
                                    <div>
                                      <p className="text-xs font-medium text-muted-foreground mb-1">步骤详情</p>
                                      <StepTimeline steps={traceDetail.steps} />
                                    </div>

                                    {/* Final response */}
                                    {traceDetail.final_response && (
                                      <div>
                                        <p className="text-xs font-medium text-muted-foreground mb-1">最终响应</p>
                                        <div className="text-sm bg-muted/50 rounded p-3 max-h-32 overflow-auto">
                                          {traceDetail.final_response}
                                        </div>
                                      </div>
                                    )}
                                  </>
                                ) : (
                                  <p className="text-sm text-muted-foreground">无法加载详情</p>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </React.Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default AgentDebugPanel;
