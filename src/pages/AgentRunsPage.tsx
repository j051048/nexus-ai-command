import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  Clock,
  DollarSign,
  GitBranch,
  Play,
  RefreshCw,
  Search,
  Wrench,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { httpClient } from '@/lib/httpClient';
import { cn } from '@/lib/utils';

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

interface AgentRun {
  id: string;
  run_id?: string;
  thread_id?: string;
  trace_id?: string;
  session_id?: string;
  scene_code?: string;
  agent_code?: string;
  status: string;
  input_summary?: string;
  output_summary?: string;
  final_response?: string;
  error?: string;
  error_message?: string;
  metadata?: Record<string, unknown>;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  duration_ms?: number;
  started_at?: string;
  finished_at?: string;
  updated_at?: string;
}

interface AgentRunSummary {
  total_runs: number;
  by_status: Record<string, number>;
  total_cost_usd: number;
  total_tokens: number;
  avg_duration_ms?: number | null;
}

interface ToolCall {
  id: string;
  tool_name: string;
  status: string;
  risk?: string;
  result_preview?: string;
  error_type?: string;
  error_message?: string;
  duration_ms?: number;
}

interface AgentEvent {
  id: number;
  event_type: string;
  node_name?: string;
  created_at?: string;
  payload?: Record<string, unknown>;
}

interface AgentRunsData {
  runs: AgentRun[];
  summary: AgentRunSummary;
}

interface AgentRunDetailData {
  run: AgentRun;
  tool_calls: ToolCall[];
  events: AgentEvent[];
}

interface CostAlert {
  level: string;
  type: string;
  message: string;
  action: string;
}

interface CostAlertsData {
  alerts: CostAlert[];
  summary: {
    total_cost_usd: number;
    high_cost_runs?: Array<{ id: string; run_id?: string; cost_usd: number; summary?: string }>;
  };
}

interface QualityTrendsData {
  days: number;
  run_count: number;
  failure_rate: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_duration_ms: number;
  eval_cases: {
    total: number;
    pending_label: number;
    by_dimension: Record<string, number>;
  };
}

interface PromptLintData {
  total_issues: number;
  error_count: number;
  warning_count: number;
  issues: Array<{ code: string; severity: string; message: string; location: string }>;
}

interface EvalCase {
  id: string;
  status: string;
  dimension: string;
  input_json?: Record<string, unknown>;
  expected_json?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
}

const STATUS_OPTIONS = ['all', 'running', 'completed', 'failed', 'error', 'cancelled'];

function formatDate(value?: string) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function formatDuration(ms?: number | null) {
  if (!ms) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function statusClass(status: string) {
  if (status === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'running') return 'border-blue-200 bg-blue-50 text-blue-700';
  if (status === 'failed' || status === 'error') return 'border-red-200 bg-red-50 text-red-700';
  return 'border-muted bg-muted text-muted-foreground';
}

function StatCard({ title, value, icon }: { title: string; value: string | number; icon: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="truncate text-2xl font-semibold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function TraceTopology({ events, toolCalls }: { events: AgentEvent[]; toolCalls: ToolCall[] }) {
  const nodes = events
    .map((event) => event.node_name || event.event_type)
    .filter(Boolean)
    .slice(0, 10);
  const uniqueNodes = Array.from(new Set(nodes));
  const fallback = toolCalls.map((call) => call.tool_name).slice(0, 10);
  const displayNodes = uniqueNodes.length ? uniqueNodes : fallback;

  if (!displayNodes.length) {
    return <p className="text-sm text-muted-foreground">暂无可视化节点</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-3">
      {displayNodes.map((node, index) => (
        <div key={`${node}-${index}`} className="flex items-center gap-2">
          <div className="rounded-md border bg-background px-2.5 py-1 text-xs font-medium">{node}</div>
          {index < displayNodes.length - 1 && <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />}
        </div>
      ))}
    </div>
  );
}

export default function AgentRunsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [summary, setSummary] = useState<AgentRunSummary | null>(null);
  const [selected, setSelected] = useState<AgentRunDetailData | null>(null);
  const [costAlerts, setCostAlerts] = useState<CostAlertsData | null>(null);
  const [qualityTrends, setQualityTrends] = useState<QualityTrendsData | null>(null);
  const [promptLint, setPromptLint] = useState<PromptLintData | null>(null);
  const [evalCases, setEvalCases] = useState<EvalCase[]>([]);
  const [status, setStatus] = useState('all');
  const [sessionId, setSessionId] = useState('');
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [replaying, setReplaying] = useState(false);

  const fetchCostAlerts = useCallback(async () => {
    try {
      const response = await httpClient.get<ApiResponse<CostAlertsData>>('/api/usage/cost-alerts', {
        params: { days: 1 },
      });
      setCostAlerts(response.data.data);
    } catch {
      setCostAlerts(null);
    }
  }, []);

  const fetchQualityOps = useCallback(async () => {
    try {
      const [trendRes, lintRes, evalRes] = await Promise.all([
        httpClient.get<ApiResponse<QualityTrendsData>>('/api/agent-runs/quality/trends', { params: { days: 30 } }),
        httpClient.get<ApiResponse<PromptLintData>>('/api/agent-runs/prompt-lint'),
        httpClient.get<ApiResponse<{ cases: EvalCase[] }>>('/api/agent/replay/eval-cases', {
          params: { status: 'pending_label', limit: 20 },
        }),
      ]);
      setQualityTrends(trendRes.data.data);
      setPromptLint(lintRes.data.data);
      setEvalCases(evalRes.data.data.cases || []);
    } catch {
      setQualityTrends(null);
      setPromptLint(null);
      setEvalCases([]);
    }
  }, []);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { limit: 80 };
      if (status !== 'all') params.status = status;
      if (sessionId.trim()) params.session_id = sessionId.trim();
      const response = await httpClient.get<ApiResponse<AgentRunsData>>('/api/agent-runs', { params });
      setRuns(response.data.data.runs || []);
      setSummary(response.data.data.summary);
      await fetchCostAlerts();
      await fetchQualityOps();
    } catch {
      toast.error('Agent Run 列表加载失败');
    } finally {
      setLoading(false);
    }
  }, [fetchCostAlerts, fetchQualityOps, sessionId, status]);

  const fetchDetail = useCallback(async (run: AgentRun) => {
    const ref = run.id || run.run_id;
    if (!ref) return;
    setDetailLoading(true);
    try {
      const response = await httpClient.get<ApiResponse<AgentRunDetailData>>(`/api/agent-runs/${ref}`);
      setSelected(response.data.data);
    } catch {
      toast.error('Agent Run 详情加载失败');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const replaySelected = useCallback(async (execute: boolean) => {
    const ref = selected?.run.id || selected?.run.run_id;
    if (!ref) return;
    setReplaying(true);
    try {
      const response = await httpClient.post<ApiResponse<Record<string, unknown>>>(
        `/api/agent-runs/${ref}/replay`,
        null,
        { params: { execute } },
      );
      toast.success(execute ? '失败运行已重新执行' : '已生成重放计划');
      console.info('Agent replay response', response.data.data);
      if (execute) await fetchRuns();
    } catch {
      toast.error('Agent Run 重放失败');
    } finally {
      setReplaying(false);
    }
  }, [fetchRuns, selected]);

  const markEvalCaseReviewed = useCallback(async (item: EvalCase) => {
    try {
      await httpClient.patch(`/api/agent/replay/eval-cases/${item.id}`, {
        status: 'labelled',
        expected_json: {
          ...(item.expected_json || {}),
          human_reviewed: true,
        },
      });
      toast.success('Eval 样本已标注');
      await fetchQualityOps();
    } catch {
      toast.error('Eval 样本标注失败');
    }
  }, [fetchQualityOps]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const statusCounts = useMemo(() => summary?.by_status || {}, [summary]);
  const selectedRun = selected?.run;
  const canReplay = selectedRun && ['failed', 'error', 'cancelled'].includes(selectedRun.status);

  return (
    <div className="space-y-5 p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal">Agent Run 管理台</h1>
          <p className="text-sm text-muted-foreground">按租户查看 LangGraph 运行、工具调用、事件流、成本告警和失败重放。</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchRuns} disabled={loading}>
          <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
          刷新
        </Button>
      </div>

      {!!costAlerts?.alerts.length && (
        <Card className="border-amber-200 bg-amber-50/60">
          <CardContent className="space-y-2 p-4">
            {costAlerts.alerts.slice(0, 3).map((alert) => (
              <div key={`${alert.type}-${alert.message}`} className="flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                <div>
                  <p className="font-medium text-amber-900">{alert.message}</p>
                  <p className="text-amber-800/80">{alert.action}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3 md:grid-cols-4">
        <StatCard title="最近运行" value={summary?.total_runs ?? 0} icon={<Activity className="h-5 w-5" />} />
        <StatCard title="运行中" value={statusCounts.running ?? 0} icon={<Clock className="h-5 w-5" />} />
        <StatCard title="失败" value={(statusCounts.failed ?? 0) + (statusCounts.error ?? 0)} icon={<AlertTriangle className="h-5 w-5" />} />
        <StatCard title="成本 USD" value={`$${(summary?.total_cost_usd ?? 0).toFixed(4)}`} icon={<DollarSign className="h-5 w-5" />} />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">质量趋势</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">30 天运行</span><span>{qualityTrends?.run_count ?? '-'}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">失败率</span><span>{qualityTrends ? `${(qualityTrends.failure_rate * 100).toFixed(1)}%` : '-'}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">待标注 Eval</span><span>{qualityTrends?.eval_cases.pending_label ?? evalCases.length}</span></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Prompt Lint</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">错误</span><span className={promptLint?.error_count ? 'text-red-600' : 'text-emerald-600'}>{promptLint?.error_count ?? '-'}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">警告</span><span>{promptLint?.warning_count ?? '-'}</span></div>
            <p className="line-clamp-2 text-xs text-muted-foreground">{promptLint?.issues?.[0]?.message || '暂无阻断级问题'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Eval 标注队列</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {evalCases.slice(0, 3).map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-2 rounded-md bg-muted/40 px-2 py-1">
                <span className="truncate">{String(item.input_json?.query || item.dimension)}</span>
                <div className="flex items-center gap-1">
                  <Badge variant="outline">{item.dimension}</Badge>
                  <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => markEvalCaseReviewed(item)}>标注</Button>
                </div>
              </div>
            ))}
            {!evalCases.length && <p className="text-muted-foreground">暂无待标注样本</p>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full md:w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((item) => (
                <SelectItem key={item} value={item}>
                  {item === 'all' ? '全部状态' : item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-9"
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              placeholder="按 session_id 过滤"
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">运行列表</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>状态</TableHead>
                  <TableHead>场景</TableHead>
                  <TableHead>摘要</TableHead>
                  <TableHead>Token</TableHead>
                  <TableHead>成本</TableHead>
                  <TableHead>耗时</TableHead>
                  <TableHead>更新时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id || run.run_id} className="cursor-pointer" onClick={() => fetchDetail(run)}>
                    <TableCell>
                      <Badge variant="outline" className={cn('whitespace-nowrap', statusClass(run.status))}>
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[120px] truncate">{run.scene_code || run.agent_code || '-'}</TableCell>
                    <TableCell className="max-w-[360px] truncate">{run.input_summary || run.output_summary || run.error_message || '-'}</TableCell>
                    <TableCell>{(run.input_tokens || 0) + (run.output_tokens || 0)}</TableCell>
                    <TableCell>${(run.cost_usd || 0).toFixed(4)}</TableCell>
                    <TableCell>{formatDuration(run.duration_ms)}</TableCell>
                    <TableCell>{formatDate(run.updated_at)}</TableCell>
                  </TableRow>
                ))}
                {!runs.length && (
                  <TableRow>
                    <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                      {loading ? '加载中...' : '暂无运行记录'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Wrench className="h-4 w-4" />
              调用详情
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedRun ? (
              <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
                选择一条运行查看工具调用和事件
              </div>
            ) : (
              <ScrollArea className="h-[680px] pr-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant="outline" className={statusClass(selectedRun.status)}>
                        {selectedRun.status}
                      </Badge>
                      {detailLoading && <span className="text-xs text-muted-foreground">更新中...</span>}
                    </div>
                    <p className="break-all text-xs text-muted-foreground">{selectedRun.run_id || selectedRun.id}</p>
                    <p className="text-sm">{selectedRun.final_response || selectedRun.output_summary || selectedRun.error_message || '无输出摘要'}</p>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" disabled={!canReplay || replaying} onClick={() => replaySelected(false)}>
                        <GitBranch className="mr-2 h-4 w-4" />
                        重放计划
                      </Button>
                      <Button size="sm" variant="outline" disabled={!canReplay || replaying} onClick={() => replaySelected(true)}>
                        <Play className="mr-2 h-4 w-4" />
                        重新执行
                      </Button>
                    </div>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium">执行拓扑</h3>
                    <TraceTopology events={selected.events} toolCalls={selected.tool_calls} />
                  </div>

                  <div className="grid gap-2 text-xs">
                    <div className="rounded-md border p-3">
                      <div className="mb-1 font-medium">Prompt / Context 巡检</div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Prompt Tokens</span><span>{String((selectedRun.metadata?.prompt_snapshot as Record<string, unknown> | undefined)?.total_tokens_estimated ?? '-')}</span></div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Prompt Warnings</span><span>{String(((selectedRun.metadata?.prompt_snapshot as Record<string, unknown> | undefined)?.warnings as unknown[] | undefined)?.length ?? 0)}</span></div>
                      <div className="flex justify-between"><span className="text-muted-foreground">Context Tokens</span><span>{String((selectedRun.metadata?.context_ledger as Record<string, unknown> | undefined)?.used_tokens ?? '-')}</span></div>
                    </div>
                    <div className="rounded-md border p-3">
                      <div className="mb-1 font-medium">成本归因</div>
                      <p className="line-clamp-4 text-muted-foreground">{JSON.stringify((selectedRun.metadata?.cost_attribution as Record<string, unknown> | undefined)?.context_providers || [])}</p>
                    </div>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium">工具调用 ({selected.tool_calls.length})</h3>
                    <div className="space-y-2">
                      {selected.tool_calls.map((call) => (
                        <div key={call.id} className="rounded-md border p-3">
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-sm font-medium">{call.tool_name}</span>
                            <Badge variant="outline">{call.status}</Badge>
                          </div>
                          <div className="mt-2 flex gap-2 text-xs text-muted-foreground">
                            <span>{call.risk || 'low'}</span>
                            <span>{formatDuration(call.duration_ms)}</span>
                          </div>
                          {(call.error_message || call.result_preview) && (
                            <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">
                              {call.error_message || call.result_preview}
                            </p>
                          )}
                        </div>
                      ))}
                      {!selected.tool_calls.length && <p className="text-sm text-muted-foreground">无工具调用</p>}
                    </div>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-medium">事件流 ({selected.events.length})</h3>
                    <div className="space-y-2">
                      {selected.events.slice(0, 80).map((event) => (
                        <div key={event.id} className="rounded-md bg-muted/50 p-3 text-xs">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">{event.node_name || event.event_type}</span>
                            <span className="text-muted-foreground">{formatDate(event.created_at)}</span>
                          </div>
                          <p className="mt-1 truncate text-muted-foreground">{JSON.stringify(event.payload || {})}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
