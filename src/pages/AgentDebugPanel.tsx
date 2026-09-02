import { getApiBaseUrl } from "@/lib/apiConfig";
/**
 * Agent 调试面板
 * HITL Admin Debug Panel for inspecting agent execution traces.
 * Shows stats overview, trace list with status filtering, expandable step detail.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import { PrecisionPageHeader } from '@/components/common/PrecisionPageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
    color: 'text-primary',
    bg: 'bg-primary/[0.08]',
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  },
  completed: {
    label: '已完成',
    color: 'text-success',
    bg: 'bg-success/[0.08]',
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  failed: {
    label: '失败',
    color: 'text-destructive',
    bg: 'bg-destructive/[0.08]',
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
  timeout: {
    label: '超时',
    color: 'text-warning',
    bg: 'bg-warning/[0.08]',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
  },
  cancelled: {
    label: '取消',
    color: 'text-muted-foreground',
    bg: 'bg-muted',
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
};

const NODE_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  router: { label: 'Router', color: 'border-primary/20 bg-primary/[0.08] text-primary' },
  plan: { label: 'Plan', color: 'border-border bg-muted text-foreground' },
  execute: { label: 'Execute', color: 'border-warning/20 bg-warning/[0.08] text-warning' },
  reflect: { label: 'Reflect', color: 'border-primary/15 bg-primary/[0.06] text-primary' },
  respond: { label: 'Respond', color: 'border-success/20 bg-success/[0.08] text-success' },
  error: { label: 'Error', color: 'border-destructive/20 bg-destructive/[0.08] text-destructive' },
};

// ─── Step Timeline ──────────────────────────────────────

function StepTimeline({ steps }: { steps: TraceStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">暂无执行步骤</p>;
  }

  return (
    <div className="space-y-0 pl-2 py-2">
      {steps.map((step, idx) => {
        const nodeConfig = NODE_TYPE_LABELS[step.node_type] || { label: step.node_type, color: 'border-border bg-muted text-muted-foreground' };
        const isLast = idx === steps.length - 1;
        return (
          <div key={step.step_id} className="relative pl-8 pb-4 group">
            {/* Timeline dot */}
            <div
              className={cn(
                'absolute left-0 top-1 flex h-6 w-6 items-center justify-center rounded-md border text-[10px] font-semibold',
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
                  <Badge variant="secondary" className="bg-success/[0.08] text-xs text-success">
                    完成
                  </Badge>
                )}
                {step.status === 'failed' && (
                  <Badge variant="secondary" className="bg-destructive/[0.08] text-xs text-destructive">
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
                <div className="rounded-md border border-destructive/20 bg-destructive/[0.06] p-2 font-mono text-xs text-destructive">
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
        const config = NODE_TYPE_LABELS[nt] || { label: nt, color: 'border-border bg-muted text-muted-foreground' };
        return (
          <React.Fragment key={idx}>
            <span
              className={cn(
                'rounded-md border px-2 py-0.5 text-[10px] font-medium',
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
    <div className="mx-auto max-w-[1480px] space-y-5 pb-20">
      <PrecisionPageHeader
        eyebrow="Agent Ops"
        title="Agent 调试面板"
        description="检视执行轨迹、质量趋势与失败节点；完整输入输出仅对管理员开放。"
        icon={Bug}
        status={{
          label: (stats?.by_status.failed ?? 0) > 0 ? '发现异常' : '链路稳定',
          detail: `${stats?.by_status.running ?? 0} 个运行中`,
          tone: (stats?.by_status.failed ?? 0) > 0 ? 'warning' : 'success',
        }}
        actions={<>
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
        </>}
      />

      <OperationalMetricStrip
        ariaLabel="Agent 调试指标"
        metrics={[
          { label: '总执行数', value: loading ? '—' : stats?.total_traces ?? 0, detail: '当前筛选范围', icon: <Activity /> },
          { label: '成功率', value: loading ? '—' : stats?.success_rate != null ? `${(stats.success_rate * 100).toFixed(1)}%` : '-', detail: '完成运行占比', tone: (stats?.success_rate ?? 1) < 0.9 ? 'warning' : 'success', icon: <CheckCircle2 /> },
          { label: '平均耗时', value: loading ? '—' : formatDuration(stats?.avg_duration_ms ?? null), detail: '端到端执行', icon: <Clock /> },
          { label: 'Token 消耗', value: loading ? '—' : stats?.total_tokens?.toLocaleString() ?? '0', detail: `$${(stats?.total_cost_usd ?? 0).toFixed(4)}`, icon: <Coins /> },
        ]}
      />

      {/* Quality Summary Cards */}
      {qualitySummary && (
        <section className="flex flex-wrap items-center gap-x-7 gap-y-2 border-b pb-3 text-xs text-muted-foreground" aria-label="Agent 质量摘要">
          <span>{qualitySummary.days} 天成功率 <strong className="ml-1 text-foreground tabular-nums">{qualitySummary.success_rate}%</strong></span>
          <span>满意度 <strong className="ml-1 text-foreground tabular-nums">{qualitySummary.satisfaction_rate}%</strong></span>
          <span className="flex items-center gap-1"><ThumbsUp className="h-3.5 w-3.5" />正面 <strong className="text-foreground tabular-nums">{qualitySummary.positive_feedback}</strong></span>
          <span className="flex items-center gap-1"><ThumbsDown className="h-3.5 w-3.5" />负面 <strong className="text-foreground tabular-nums">{qualitySummary.negative_feedback}</strong></span>
        </section>
      )}

      {/* Quality Trend Chart */}
      {qualityTrend.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              质量趋势（最近 30 天）
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
                  <CartesianGrid strokeDasharray="2 4" className="stroke-border/70" vertical={false} />
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
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={false}
                    name="执行数"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="success_rate"
                    stroke="hsl(var(--success))"
                    strokeWidth={2}
                    dot={false}
                    name="成功率%"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="satisfaction"
                    stroke="hsl(var(--warning))"
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
                                        <div className="max-h-32 overflow-auto rounded-md border bg-muted/40 p-3 text-sm">
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
