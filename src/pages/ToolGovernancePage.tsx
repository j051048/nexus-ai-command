import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Download, RefreshCw, Search, ShieldAlert, Tags, TestTube2, Wrench } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { httpClient } from '@/lib/httpClient';
import { cn } from '@/lib/utils';

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

interface ToolManifest {
  name: string;
  category?: string;
  description?: string;
  required_role?: string;
  risk?: string;
  owner?: string;
  timeout_s?: number | null;
  idempotent?: boolean;
  side_effect?: boolean;
  is_irreversible?: boolean;
}

interface GovernanceAudit {
  risk_counts: Record<string, number>;
  category_counts: Record<string, number>;
  missing_owner: string[];
  default_owner: string[];
  missing_timeout: string[];
  missing_idempotency: string[];
  side_effect_without_risk: string[];
  high_risk_tools: string[];
  findings: Record<string, number>;
}

interface ToolRagStats {
  tool_count?: number;
  indexed_tools?: number;
  embedding_provider?: string;
  age_s?: number;
}

interface FixSuggestion {
  tool_name: string;
  category?: string;
  patch: Record<string, string | number | boolean>;
  reasons: string[];
  example_decorator_args: string;
}

interface GovernanceData {
  tools: ToolManifest[];
  count: number;
  audit: GovernanceAudit;
  fix_suggestions?: FixSuggestion[];
  tool_rag: ToolRagStats;
}

interface RagEvalData {
  cases: Array<{
    query: string;
    expected: string[];
    retrieved: Array<[string, number]>;
    matched: string[];
    passed: boolean;
  }>;
  summary: {
    total: number;
    passed: number;
    top_k_recall: number;
  };
}

function riskClass(risk?: string) {
  if (risk === 'critical' || risk === 'high') return 'border-red-200 bg-red-50 text-red-700';
  if (risk === 'medium') return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-emerald-200 bg-emerald-50 text-emerald-700';
}

function downloadJson(data: GovernanceData | null) {
  if (!data) return;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `tool-governance-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
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

export default function ToolGovernancePage() {
  const [data, setData] = useState<GovernanceData | null>(null);
  const [ragEval, setRagEval] = useState<RagEvalData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [query, setQuery] = useState('');
  const [risk, setRisk] = useState('all');

  const fetchGovernance = useCallback(async () => {
    setLoading(true);
    try {
      const response = await httpClient.get<ApiResponse<GovernanceData>>('/api/tools/governance');
      setData(response.data.data);
    } catch {
      toast.error('Tool 治理清单加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshToolRag = useCallback(async () => {
    setRefreshing(true);
    try {
      await httpClient.post('/api/tools/rag/refresh');
      toast.success('Tool RAG 索引已刷新');
      await fetchGovernance();
    } catch {
      toast.error('Tool RAG 刷新失败');
    } finally {
      setRefreshing(false);
    }
  }, [fetchGovernance]);

  const evaluateToolRag = useCallback(async () => {
    setEvaluating(true);
    try {
      const response = await httpClient.get<ApiResponse<RagEvalData>>('/api/tools/rag/evaluate');
      setRagEval(response.data.data);
      toast.success('Tool RAG 评估完成');
    } catch {
      toast.error('Tool RAG 评估失败');
    } finally {
      setEvaluating(false);
    }
  }, []);

  useEffect(() => {
    fetchGovernance();
  }, [fetchGovernance]);

  const tools = useMemo(() => data?.tools || [], [data?.tools]);
  const filteredTools = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return tools.filter((tool) => {
      const matchesRisk = risk === 'all' || (tool.risk || 'low') === risk;
      const matchesKeyword =
        !keyword ||
        tool.name.toLowerCase().includes(keyword) ||
        (tool.category || '').toLowerCase().includes(keyword) ||
        (tool.owner || '').toLowerCase().includes(keyword);
      return matchesRisk && matchesKeyword;
    });
  }, [query, risk, tools]);

  const audit = data?.audit;
  const riskOptions = Object.keys(audit?.risk_counts || {});
  const fixSuggestions = data?.fix_suggestions || [];

  return (
    <div className="space-y-5 p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal">Tool 治理清单</h1>
          <p className="text-sm text-muted-foreground">审计 Agent Tools 的风险、负责人、幂等性、超时、修复建议和 Tool RAG 召回质量。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={fetchGovernance} disabled={loading}>
            <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
            刷新
          </Button>
          <Button variant="outline" size="sm" onClick={refreshToolRag} disabled={refreshing}>
            <Wrench className={cn('mr-2 h-4 w-4', refreshing && 'animate-pulse')} />
            重建索引
          </Button>
          <Button variant="outline" size="sm" onClick={evaluateToolRag} disabled={evaluating}>
            <TestTube2 className={cn('mr-2 h-4 w-4', evaluating && 'animate-pulse')} />
            评估召回
          </Button>
          <Button variant="outline" size="sm" onClick={() => downloadJson(data)} disabled={!data}>
            <Download className="mr-2 h-4 w-4" />
            导出
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <StatCard title="工具总数" value={data?.count ?? 0} icon={<Wrench className="h-5 w-5" />} />
        <StatCard title="高风险" value={audit?.findings.high_risk_tools ?? 0} icon={<ShieldAlert className="h-5 w-5" />} />
        <StatCard title="修复建议" value={fixSuggestions.length} icon={<Tags className="h-5 w-5" />} />
        <StatCard title="RAG 召回" value={ragEval ? `${Math.round(ragEval.summary.top_k_recall * 100)}%` : '-'} icon={<Search className="h-5 w-5" />} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card>
          <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center">
            <Select value={risk} onValueChange={setRisk}>
              <SelectTrigger className="w-full md:w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部风险</SelectItem>
                {riskOptions.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索工具、分类或 owner"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-muted-foreground">已索引工具</p>
                <p className="font-medium">{data?.tool_rag?.tool_count ?? data?.tool_rag?.indexed_tools ?? 0}</p>
              </div>
              <div>
                <p className="text-muted-foreground">索引年龄</p>
                <p className="font-medium">{data?.tool_rag?.age_s ? `${Math.round(data.tool_rag.age_s)}s` : '-'}</p>
              </div>
              <div>
                <p className="text-muted-foreground">缺 timeout</p>
                <p className="font-medium">{audit?.findings.missing_timeout ?? 0}</p>
              </div>
              <div>
                <p className="text-muted-foreground">缺幂等约束</p>
                <p className="font-medium">{audit?.findings.missing_idempotency ?? 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">工具明细</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>工具</TableHead>
                  <TableHead>分类</TableHead>
                  <TableHead>风险</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>超时</TableHead>
                  <TableHead>幂等</TableHead>
                  <TableHead>副作用</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTools.map((tool) => (
                  <TableRow key={tool.name}>
                    <TableCell className="max-w-[260px]">
                      <div className="truncate font-medium">{tool.name}</div>
                      <div className="line-clamp-1 text-xs text-muted-foreground">{tool.description || '-'}</div>
                    </TableCell>
                    <TableCell>{tool.category || 'general'}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={riskClass(tool.risk)}>
                        {tool.risk || 'low'}
                      </Badge>
                    </TableCell>
                    <TableCell>{tool.owner || '-'}</TableCell>
                    <TableCell>{tool.timeout_s ? `${tool.timeout_s}s` : '-'}</TableCell>
                    <TableCell>{tool.idempotent ? '是' : '否'}</TableCell>
                    <TableCell>{tool.side_effect || tool.is_irreversible ? '是' : '否'}</TableCell>
                  </TableRow>
                ))}
                {!filteredTools.length && (
                  <TableRow>
                    <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                      {loading ? '加载中...' : '暂无匹配工具'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">自动修复建议</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {fixSuggestions.slice(0, 8).map((suggestion) => (
                <div key={suggestion.tool_name} className="rounded-md border p-3">
                  <p className="truncate text-sm font-medium">{suggestion.tool_name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{suggestion.example_decorator_args}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {Object.keys(suggestion.patch).map((key) => (
                      <Badge key={key} variant="secondary">{key}</Badge>
                    ))}
                  </div>
                </div>
              ))}
              {!fixSuggestions.length && <p className="text-sm text-muted-foreground">暂无修复建议</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">RAG 评估</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {ragEval?.cases.slice(0, 6).map((item) => (
                <div key={item.query} className="rounded-md bg-muted/50 p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{item.query}</span>
                    <Badge variant={item.passed ? 'secondary' : 'destructive'}>
                      {item.passed ? '命中' : '未命中'}
                    </Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground">期望: {item.expected.join(', ')}</p>
                  <p className="mt-1 text-muted-foreground">命中: {item.matched.join(', ') || '-'}</p>
                </div>
              ))}
              {!ragEval && <p className="text-sm text-muted-foreground">点击“评估召回”运行内置评估集。</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
