/**
 * PromptManagement — Prompt 版本管理 + A/B 测试管理界面
 */

import React, { useState, useEffect, useCallback } from 'react';
import { aiClient } from '@/api/aiClient';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import {
  Plus,
  History,
  FlaskConical,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  Loader2,
  FileText,
  BarChart3,
  Pencil,
} from 'lucide-react';

// ─── Types ──────────────────────────────────────────────────

interface PromptVersion {
  id: string;
  version: number;
  content: string;
  status: 'draft' | 'active' | 'archived';
  created_at: string;
  updated_by?: string;
  change_note?: string;
}

interface PromptTemplate {
  id: string;
  name: string;
  description: string;
  current_version: number;
  status: 'active' | 'testing' | 'inactive';
  created_at: string;
  updated_at: string;
  versions?: PromptVersion[];
}

interface ABTest {
  id: string;
  prompt_id: string;
  prompt_name: string;
  version_a: number;
  version_b: number;
  traffic_split: number; // version_a 的流量百分比
  status: 'running' | 'completed' | 'paused';
  metrics: {
    version_a: { calls: number; avg_latency_ms: number; success_rate: number; user_rating: number };
    version_b: { calls: number; avg_latency_ms: number; success_rate: number; user_rating: number };
  };
  started_at: string;
  ended_at?: string;
}

// ─── Status Badge Map ───────────────────────────────────────

const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  active: 'default',
  testing: 'secondary',
  inactive: 'outline',
  running: 'default',
  completed: 'secondary',
  paused: 'outline',
  draft: 'outline',
  archived: 'destructive',
};

const statusLabel: Record<string, string> = {
  active: '启用中',
  testing: '测试中',
  inactive: '未启用',
  running: '进行中',
  completed: '已完成',
  paused: '已暂停',
  draft: '草稿',
  archived: '已归档',
};

// ─── Mock Data (后端未就绪时) ────────────────────────────────

const MOCK_PROMPTS: PromptTemplate[] = [
  {
    id: 'p1',
    name: '销售助手系统提示词',
    description: '用于销售场景的主系统提示词，覆盖线索分析、客户跟进等功能',
    current_version: 3,
    status: 'active',
    created_at: '2026-01-15T08:00:00Z',
    updated_at: '2026-03-10T14:30:00Z',
    versions: [
      { id: 'v3', version: 3, content: '你是一个专业的销售顾问 AI...（v3 增强版）', status: 'active', created_at: '2026-03-10T14:30:00Z', change_note: '增加竞品分析能力' },
      { id: 'v2', version: 2, content: '你是一个专业的销售顾问 AI...（v2）', status: 'archived', created_at: '2026-02-20T10:00:00Z', change_note: '优化输出格式' },
      { id: 'v1', version: 1, content: '你是一个销售助手...（v1 初版）', status: 'archived', created_at: '2026-01-15T08:00:00Z', change_note: '初始版本' },
    ],
  },
  {
    id: 'p2',
    name: 'OA 审批分析提示词',
    description: '审批流程中 AI 辅助审核的提示词模板',
    current_version: 2,
    status: 'testing',
    created_at: '2026-02-01T09:00:00Z',
    updated_at: '2026-03-05T16:00:00Z',
    versions: [
      { id: 'v2b', version: 2, content: '请审核以下审批申请...（v2）', status: 'active', created_at: '2026-03-05T16:00:00Z', change_note: 'A/B 测试候选' },
      { id: 'v1b', version: 1, content: '请审核以下审批申请...（v1）', status: 'active', created_at: '2026-02-01T09:00:00Z', change_note: '初始版本' },
    ],
  },
  {
    id: 'p3',
    name: 'VMD 内容生成提示词',
    description: '虚拟市场部生成营销内容时使用的提示词',
    current_version: 1,
    status: 'active',
    created_at: '2026-02-28T11:00:00Z',
    updated_at: '2026-02-28T11:00:00Z',
    versions: [
      { id: 'v1c', version: 1, content: '你是一个营销内容专家...', status: 'active', created_at: '2026-02-28T11:00:00Z', change_note: '初始版本' },
    ],
  },
];

const MOCK_AB_TESTS: ABTest[] = [
  {
    id: 'ab1',
    prompt_id: 'p2',
    prompt_name: 'OA 审批分析提示词',
    version_a: 1,
    version_b: 2,
    traffic_split: 50,
    status: 'running',
    metrics: {
      version_a: { calls: 156, avg_latency_ms: 1200, success_rate: 0.94, user_rating: 4.2 },
      version_b: { calls: 148, avg_latency_ms: 980, success_rate: 0.97, user_rating: 4.6 },
    },
    started_at: '2026-03-05T16:00:00Z',
  },
];

// ─── Component ──────────────────────────────────────────────

export default function PromptManagement() {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [abTests, setAbTests] = useState<ABTest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('prompts');

  // Dialog states
  const [showNewVersion, setShowNewVersion] = useState(false);
  const [showABConfig, setShowABConfig] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [newVersionContent, setNewVersionContent] = useState('');
  const [newVersionNote, setNewVersionNote] = useState('');
  const [abVersionA, setAbVersionA] = useState<number>(0);
  const [abVersionB, setAbVersionB] = useState<number>(0);
  const [abTrafficSplit, setAbTrafficSplit] = useState(50);
  const [isSaving, setIsSaving] = useState(false);

  // ─── Fetch Data ─────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [promptsRes, abRes] = await Promise.allSettled([
        aiClient.fetch<PromptTemplate[]>('api/prompts/versions', { _silentError: true }),
        aiClient.fetch<ABTest[]>('api/prompts/ab-tests', { _silentError: true }),
      ]);

      if (promptsRes.status === 'fulfilled') {
        const data = promptsRes.value;
        setPrompts(Array.isArray(data) ? data : []);
      } else {
        setPrompts(MOCK_PROMPTS);
      }

      if (abRes.status === 'fulfilled') {
        const data = abRes.value;
        setAbTests(Array.isArray(data) ? data : []);
      } else {
        setAbTests(MOCK_AB_TESTS);
      }
    } catch {
      setPrompts(MOCK_PROMPTS);
      setAbTests(MOCK_AB_TESTS);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── Actions ────────────────────────────────────────────

  const handleCreateVersion = async () => {
    if (!selectedPrompt || !newVersionContent.trim()) return;

    setIsSaving(true);
    try {
      await aiClient.post('api/prompts/versions', {
        prompt_id: selectedPrompt.id,
        content: newVersionContent,
        change_note: newVersionNote,
      }, { _silentError: true });
      toast.success('新版本创建成功');
      fetchData();
    } catch {
      // Mock: 在本地添加新版本
        const newVersion: PromptVersion = {
          id: `v-${Date.now()}`,
          version: selectedPrompt.current_version + 1,
          content: newVersionContent,
          status: 'draft',
          created_at: new Date().toISOString(),
          change_note: newVersionNote || '新版本',
        };
        setPrompts((prev) =>
          prev.map((p) =>
            p.id === selectedPrompt.id
              ? {
                  ...p,
                  current_version: newVersion.version,
                  updated_at: newVersion.created_at,
                  versions: [newVersion, ...(p.versions ?? [])],
                }
              : p,
          ),
        );
        toast.success('新版本已创建（本地模式）');
    } finally {
      setIsSaving(false);
      setShowNewVersion(false);
      setNewVersionContent('');
      setNewVersionNote('');
    }
  };

  const handleStartABTest = async () => {
    if (!selectedPrompt || abVersionA === abVersionB) {
      toast.error('请选择两个不同的版本');
      return;
    }

    setIsSaving(true);
    try {
      await aiClient.post('api/prompts/ab-tests', {
        prompt_id: selectedPrompt.id,
        version_a: abVersionA,
        version_b: abVersionB,
        traffic_split: abTrafficSplit,
      }, { _silentError: true });
      toast.success('A/B 测试已启动');
      fetchData();
    } catch {
      // Mock
      const newTest: ABTest = {
          id: `ab-${Date.now()}`,
          prompt_id: selectedPrompt.id,
          prompt_name: selectedPrompt.name,
          version_a: abVersionA,
          version_b: abVersionB,
          traffic_split: abTrafficSplit,
          status: 'running',
          metrics: {
            version_a: { calls: 0, avg_latency_ms: 0, success_rate: 0, user_rating: 0 },
            version_b: { calls: 0, avg_latency_ms: 0, success_rate: 0, user_rating: 0 },
          },
          started_at: new Date().toISOString(),
        };
        setAbTests((prev) => [newTest, ...prev]);
        setPrompts((prev) =>
          prev.map((p) =>
            p.id === selectedPrompt.id ? { ...p, status: 'testing' as const } : p,
          ),
        );
        toast.success('A/B 测试已启动（本地模式）');
    } finally {
      setIsSaving(false);
      setShowABConfig(false);
    }
  };

  const handleRollback = async (promptId: string, version: number) => {
    try {
      await aiClient.post(`api/prompts/versions/${promptId}/rollback`, {
        target_version: version,
      }, { _silentError: true });
      toast.success(`已回滚到版本 ${version}`);
      fetchData();
    } catch {
      // Mock
      setPrompts((prev) =>
        prev.map((p) =>
          p.id === promptId ? { ...p, current_version: version, updated_at: new Date().toISOString() } : p,
        ),
      );
      toast.success(`已回滚到版本 ${version}（本地模式）`);
    }
    }
  };

  // ─── Render ─────────────────────────────────────────────

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Prompt 管理</h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理 AI 提示词模板的版本与 A/B 测试
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="prompts" className="gap-1.5">
            <FileText className="w-4 h-4" />
            提示词模板
          </TabsTrigger>
          <TabsTrigger value="ab-tests" className="gap-1.5">
            <FlaskConical className="w-4 h-4" />
            A/B 测试
          </TabsTrigger>
        </TabsList>

        {/* ── Prompts Tab ──────────────────────────────── */}
        <TabsContent value="prompts" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <TableHead>名称</TableHead>
                    <TableHead>描述</TableHead>
                    <TableHead className="text-center">当前版本</TableHead>
                    <TableHead className="text-center">状态</TableHead>
                    <TableHead>更新时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {prompts.map((prompt) => (
                    <React.Fragment key={prompt.id}>
                      {/* Main row */}
                      <TableRow
                        className="cursor-pointer hover:bg-accent/50"
                        onClick={() =>
                          setExpandedId(expandedId === prompt.id ? null : prompt.id)
                        }
                      >
                        <TableCell>
                          {expandedId === prompt.id ? (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{prompt.name}</TableCell>
                        <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                          {prompt.description}
                        </TableCell>
                        <TableCell className="text-center">v{prompt.current_version}</TableCell>
                        <TableCell className="text-center">
                          <Badge variant={statusVariant[prompt.status] ?? 'outline'}>
                            {statusLabel[prompt.status] ?? prompt.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(prompt.updated_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs gap-1"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedPrompt(prompt);
                                setNewVersionContent(
                                  prompt.versions?.[0]?.content ?? '',
                                );
                                setShowNewVersion(true);
                              }}
                            >
                              <Plus className="w-3 h-3" />
                              新版本
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs gap-1"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedPrompt(prompt);
                                const versions = prompt.versions ?? [];
                                setAbVersionA(versions[1]?.version ?? 1);
                                setAbVersionB(versions[0]?.version ?? 2);
                                setAbTrafficSplit(50);
                                setShowABConfig(true);
                              }}
                            >
                              <FlaskConical className="w-3 h-3" />
                              A/B 测试
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>

                      {/* Version history rows */}
                      {expandedId === prompt.id &&
                        prompt.versions?.map((ver) => (
                          <TableRow
                            key={ver.id}
                            className="bg-muted/30 hover:bg-muted/50"
                          >
                            <TableCell />
                            <TableCell className="pl-8">
                              <div className="flex items-center gap-2">
                                <History className="w-3.5 h-3.5 text-muted-foreground" />
                                <span className="text-sm">v{ver.version}</span>
                              </div>
                            </TableCell>
                            <TableCell
                              className="text-sm text-muted-foreground max-w-[200px] truncate"
                              title={ver.content}
                            >
                              {ver.change_note ?? ver.content.slice(0, 60)}
                            </TableCell>
                            <TableCell />
                            <TableCell className="text-center">
                              <Badge
                                variant={statusVariant[ver.status] ?? 'outline'}
                                className="text-[10px]"
                              >
                                {statusLabel[ver.status] ?? ver.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDate(ver.created_at)}
                            </TableCell>
                            <TableCell className="text-right">
                              {ver.version !== prompt.current_version && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 text-xs gap-1"
                                  onClick={() =>
                                    handleRollback(prompt.id, ver.version)
                                  }
                                >
                                  <RotateCcw className="w-3 h-3" />
                                  回滚
                                </Button>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>

              {prompts.length === 0 && (
                <div className="py-12 text-center text-muted-foreground">
                  暂无提示词模板
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── A/B Tests Tab ────────────────────────────── */}
        <TabsContent value="ab-tests" className="mt-4">
          <div className="grid gap-4">
            {abTests.map((test) => (
              <Card key={test.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <FlaskConical className="w-4 h-4 text-primary" />
                      {test.prompt_name}
                      <span className="text-sm font-normal text-muted-foreground">
                        v{test.version_a} vs v{test.version_b}
                      </span>
                    </CardTitle>
                    <Badge variant={statusVariant[test.status] ?? 'outline'}>
                      {statusLabel[test.status] ?? test.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Traffic split */}
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                      <span>流量分配</span>
                      <span>
                        v{test.version_a}: {test.traffic_split}% / v{test.version_b}:{' '}
                        {100 - test.traffic_split}%
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden flex">
                      <div
                        className="bg-primary h-full rounded-l-full"
                        style={{ width: `${test.traffic_split}%` }}
                      />
                      <div
                        className="bg-primary/40 h-full rounded-r-full"
                        style={{ width: `${100 - test.traffic_split}%` }}
                      />
                    </div>
                  </div>

                  {/* Metrics comparison */}
                  <div className="grid grid-cols-2 gap-4">
                    {(['version_a', 'version_b'] as const).map((vKey) => {
                      const label =
                        vKey === 'version_a'
                          ? `v${test.version_a}`
                          : `v${test.version_b}`;
                      const m = test.metrics[vKey];
                      return (
                        <div
                          key={vKey}
                          className="rounded-lg border p-3 space-y-2"
                        >
                          <div className="text-sm font-medium">{label}</div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-muted-foreground">调用次数</span>
                              <div className="font-semibold">{m.calls}</div>
                            </div>
                            <div>
                              <span className="text-muted-foreground">平均延迟</span>
                              <div className="font-semibold">{m.avg_latency_ms}ms</div>
                            </div>
                            <div>
                              <span className="text-muted-foreground">成功率</span>
                              <div className="font-semibold">
                                {(m.success_rate * 100).toFixed(1)}%
                              </div>
                            </div>
                            <div>
                              <span className="text-muted-foreground">用户评分</span>
                              <div className="font-semibold">{m.user_rating.toFixed(1)}</div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="mt-3 text-xs text-muted-foreground">
                    开始时间: {formatDate(test.started_at)}
                    {test.ended_at && ` | 结束时间: ${formatDate(test.ended_at)}`}
                  </div>
                </CardContent>
              </Card>
            ))}

            {abTests.length === 0 && (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  暂无 A/B 测试
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* ── New Version Dialog ─────────────────────────── */}
      <Dialog open={showNewVersion} onOpenChange={setShowNewVersion}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>创建新版本</DialogTitle>
            <DialogDescription>
              为 "{selectedPrompt?.name}" 创建新的提示词版本
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium mb-1 block">变更说明</label>
              <Input
                placeholder="本次修改的目的..."
                value={newVersionNote}
                onChange={(e) => setNewVersionNote(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">提示词内容</label>
              <textarea
                className="w-full min-h-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="输入提示词内容..."
                value={newVersionContent}
                onChange={(e) => setNewVersionContent(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewVersion(false)}>
              取消
            </Button>
            <Button
              onClick={handleCreateVersion}
              disabled={!newVersionContent.trim() || isSaving}
            >
              {isSaving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              创建版本
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── A/B Test Config Dialog ─────────────────────── */}
      <Dialog open={showABConfig} onOpenChange={setShowABConfig}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>配置 A/B 测试</DialogTitle>
            <DialogDescription>
              为 "{selectedPrompt?.name}" 设置 A/B 测试参数
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-1 block">版本 A</label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={abVersionA}
                  onChange={(e) => setAbVersionA(Number(e.target.value))}
                >
                  {selectedPrompt?.versions?.map((v) => (
                    <option key={v.id} value={v.version}>
                      v{v.version} - {v.change_note ?? ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">版本 B</label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={abVersionB}
                  onChange={(e) => setAbVersionB(Number(e.target.value))}
                >
                  {selectedPrompt?.versions?.map((v) => (
                    <option key={v.id} value={v.version}>
                      v{v.version} - {v.change_note ?? ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">
                流量分配 (版本 A: {abTrafficSplit}%)
              </label>
              <input
                type="range"
                min={10}
                max={90}
                step={10}
                value={abTrafficSplit}
                onChange={(e) => setAbTrafficSplit(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>版本 A: {abTrafficSplit}%</span>
                <span>版本 B: {100 - abTrafficSplit}%</span>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowABConfig(false)}>
              取消
            </Button>
            <Button
              onClick={handleStartABTest}
              disabled={abVersionA === abVersionB || isSaving}
            >
              {isSaving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              启动 A/B 测试
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
