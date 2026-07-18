/**
 * LLM 模型管理页面
 * 模型CRUD + 连通性测试 + 调度规则 + 用量统计
 */

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  Plus,
  Cpu,
  Star,
  Pencil,
  Trash2,
  Loader2,
  Zap,
  TestTube,
  CheckCircle2,
  Settings2,
  BarChart3,
  ShoppingBag,
  Search,
  ArrowRight,
  Info,
  Wrench,
  MessageSquare,
  Hash,
  RefreshCw,
  ShieldCheck,
  Route,
  Play,
  LockKeyhole,
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  useLLMModels,
  useCreateLLMModel,
  useUpdateLLMModel,
  useDeleteLLMModel,
  useTestLLMModel,
  useScheduleRules,
  useCreateScheduleRule,
  useUpdateScheduleRule,
  useDeleteScheduleRule,
  useModelUsageStats,
  useFetchAvailableModels,
  useQuickAddModel,
  type LLMModel,
  type ScheduleRule,
  type AvailableModel,
  type ModelCategory,
} from '@/hooks/useVMD';
import { chartColors, CHART_COLORS } from '@/lib/chartColors';
import { toast } from 'sonner';
import {
  useAIExecutionPolicy,
  useAIServiceOverview,
  usePolicyWorkers,
  useSimulateAIExecutionPolicy,
  type PolicySimulationResult,
} from '@/hooks/useAIExecutionPolicy';
import { ModelEditorDialog } from '@/components/ai/model-management/ModelEditorDialog';
import { QuickAddModelDialog } from '@/components/ai/model-management/QuickAddModelDialog';
import {
  EMPTY_MODEL,
  MODEL_PROVIDER_NAMES,
  MODEL_TAG_COLORS,
  MODEL_TIERS,
  formatContextWindow,
} from '@/components/ai/model-management/modelManagementConfig';

export default function LLMModelManagement() {
  const [activeTab, setActiveTab] = useState('overview');
  const [editOpen, setEditOpen] = useState(false);
  const [editModel, setEditModel] = useState<Partial<LLMModel>>(EMPTY_MODEL);
  const [isEditing, setIsEditing] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms: number } | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // Model marketplace state
  const [marketSearch, setMarketSearch] = useState('');
  const [marketTypeFilter, setMarketTypeFilter] = useState<string | undefined>(undefined);
  const [marketTagFilter, setMarketTagFilter] = useState<string | undefined>(undefined);
  const [confirmAddModel, setConfirmAddModel] = useState<AvailableModel | null>(null);
  const [simulationQuery, setSimulationQuery] = useState('审批一笔 12000 元差旅报销并检查异常');
  const [simulationResult, setSimulationResult] = useState<PolicySimulationResult | null>(null);

  // Queries
  const { data: models, isLoading: modelsLoading } = useLLMModels();
  const { data: rules, isLoading: rulesLoading } = useScheduleRules();
  const { data: usageStats } = useModelUsageStats('week');
  const { data: availableData, isLoading: marketLoading, refetch: refetchMarket } = useFetchAvailableModels({
    search: marketSearch || undefined,
    type: marketTypeFilter,
    tag: marketTagFilter,
  });
  const { data: policyData } = useAIExecutionPolicy();
  const { data: serviceOverview } = useAIServiceOverview();
  const { data: policyWorkers } = usePolicyWorkers();
  const simulatePolicy = useSimulateAIExecutionPolicy();

  // Mutations
  const createModel = useCreateLLMModel();
  const updateModel = useUpdateLLMModel();
  const deleteModel = useDeleteLLMModel();
  const testModel = useTestLLMModel();
  const quickAdd = useQuickAddModel();
  const createRule = useCreateScheduleRule();
  const updateRule = useUpdateScheduleRule();
  const deleteRule = useDeleteScheduleRule();

  // All unique tags from available models for filter chips
  const allTags = useMemo(() => {
    if (!availableData?.categories) return [];
    const tagSet = new Set<string>();
    for (const cat of availableData.categories) {
      for (const m of cat.models) {
        for (const t of m.tags) tagSet.add(t);
      }
    }
    return Array.from(tagSet);
  }, [availableData]);

  const handleQuickAdd = async () => {
    if (!confirmAddModel) return;
    try {
      await quickAdd.mutateAsync(confirmAddModel);
      setConfirmAddModel(null);
    } catch {
      // Error toast handled in mutation
    }
  };

  const handleOpenCreate = () => {
    setEditModel({ ...EMPTY_MODEL });
    setIsEditing(false);
    setTestResult(null);
    setEditOpen(true);
  };

  const handleOpenEdit = (model: LLMModel) => {
    setEditModel({ ...model, api_key: '••••••••' });
    setIsEditing(true);
    setTestResult(null);
    setEditOpen(true);
  };

  const handleSave = async () => {
    if (!editModel.model_code || !editModel.model_name) {
      toast.error('请填写模型编码和名称');
      return;
    }
    if (!editModel.api_base_url) {
      toast.error('请填写 API Base URL');
      return;
    }
    if (!isEditing && !editModel.api_key) {
      toast.error('请填写 API Key');
      return;
    }

    // Map frontend field names to backend field names
    const payload: Record<string, unknown> = {
      model_code: editModel.model_code,
      model_name: editModel.model_name,
      provider_type: editModel.provider_type || 'openai',
      adapter_code: editModel.provider_type || 'openai',
      api_base_url: editModel.api_base_url,
      model_id: editModel.model_id || null,
      model_type: editModel.model_type || 'chat',
      timeout_ms: editModel.timeout_ms || 30000,
      max_tokens: editModel.max_tokens || 4096,
      context_window: editModel.context_window || 8192,
      supports_tools: editModel.supports_tools ?? true,
      supports_streaming: editModel.supports_streaming ?? true,
      input_price_per_1m: (editModel.input_price || 0) * 1000,
      output_price_per_1m: (editModel.output_price || 0) * 1000,
      status: editModel.is_active === false ? 'disabled' : 'enabled',
    };
    if (editModel.api_key && editModel.api_key !== '••••••••') {
      payload.api_key = editModel.api_key;
    }
    if (editModel.secret_key) {
      payload.secret_key = editModel.secret_key;
    }

    try {
      if (isEditing && editModel.id) {
        await updateModel.mutateAsync({ ...payload, id: editModel.id } as LLMModel & { id: string });
      } else {
        await createModel.mutateAsync(payload as Partial<LLMModel>);
      }
      setEditOpen(false);
    } catch {
      // onError handler in mutation already shows toast
    }
  };

  const handleTest = async (modelId: string) => {
    setTestingId(modelId);
    try {
      const result = await testModel.mutateAsync(modelId);
      toast.success(`连通性测试成功，延迟: ${result.latency_ms}ms`);
      if (editOpen) setTestResult(result);
    } catch {
      toast.error('连通性测试失败');
      if (editOpen) setTestResult({ success: false, latency_ms: 0 });
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (model: LLMModel) => {
    if (!confirm(`确定要删除模型 "${model.model_name}" 吗？`)) return;
    await deleteModel.mutateAsync(model.id);
  };

  const handleToggleActive = async (model: LLMModel) => {
    await updateModel.mutateAsync({ id: model.id, is_active: !model.is_active });
  };

  // ── Tier-based schedule rule helpers ──
  const getRuleForTier = (tier: string) => {
    return rules?.find((r) => r.complexity_tier === tier && r.scene_code === '*');
  };

  const handleSaveTierRule = async (tier: string, primaryModelId: string, backupModelId: string) => {
    const existing = getRuleForTier(tier);
    try {
      if (existing) {
        await updateRule.mutateAsync({
          id: existing.id,
          primary_model_id: primaryModelId,
          backup_model_id: backupModelId || undefined,
        });
      } else {
        await createRule.mutateAsync({
          rule_name: `默认${MODEL_TIERS.find((item) => item.value === tier)?.label || tier}规则`,
          scene_code: '*',
          agent_code: '*',
          primary_model_id: primaryModelId,
          backup_model_id: backupModelId || undefined,
          complexity_tier: tier,
          priority: MODEL_TIERS.findIndex((item) => item.value === tier),
        });
      }
    } catch {
      // Error toast handled in mutation
    }
  };

  const handleDeleteTierRule = async (tier: string) => {
    const existing = getRuleForTier(tier);
    if (existing && confirm('确定要删除该层级的模型配置吗？将回退到系统默认。')) {
      try {
        await deleteRule.mutateAsync(existing.id);
      } catch {
        // Error toast handled in mutation
      }
    }
  };

  const handleSimulate = async () => {
    if (!simulationQuery.trim()) return;
    try {
      const result = await simulatePolicy.mutateAsync([
        {
          query: simulationQuery.trim(),
          complexity: 'moderate',
          scene_code: 'chat',
          requires_tools: true,
        },
      ]);
      setSimulationResult(result[0] || null);
    } catch {
      toast.error('策略仿真失败，请稍后重试');
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI 服务管理</h1>
          <p className="text-muted-foreground">查看运行状态、成本策略与高级连接配置</p>
        </div>
        {activeTab === 'models' && (
          <Button onClick={handleOpenCreate}>
            <Plus className="w-4 h-4 mr-2" />
            新增连接
          </Button>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview" className="gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" /> 运行概览
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> 成本与用量
          </TabsTrigger>
          <TabsTrigger value="models" className="gap-1.5">
            <LockKeyhole className="w-3.5 h-3.5" /> 高级治理
          </TabsTrigger>
        </TabsList>

        {['models', 'marketplace', 'rules'].includes(activeTab) && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-b border-border pb-3">
            <span className="mr-2 text-xs text-muted-foreground">高级治理</span>
            <Button
              size="sm"
              variant={activeTab === 'models' ? 'secondary' : 'ghost'}
              onClick={() => setActiveTab('models')}
            >
              连接配置
            </Button>
            <Button
              size="sm"
              variant={activeTab === 'marketplace' ? 'secondary' : 'ghost'}
              onClick={() => setActiveTab('marketplace')}
            >
              服务目录
            </Button>
            <Button
              size="sm"
              variant={activeTab === 'rules' ? 'secondary' : 'ghost'}
              onClick={() => setActiveTab('rules')}
            >
              历史调度规则
            </Button>
          </div>
        )}

        <TabsContent value="overview" className="mt-5 space-y-8">
          <section>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <div>
                <h2 className="text-base font-semibold">生产服务</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  对话统一使用低成本主模型，高价模型只允许人工启用。
                </p>
              </div>
              <Badge variant="outline" className="gap-1.5 font-normal text-success">
                <span className="h-1.5 w-1.5 rounded-full bg-success" />
                服务正常
              </Badge>
            </div>
            <div className="divide-y divide-border">
              {(serviceOverview?.roles || []).map((role) => (
                <div key={role.code} className="grid gap-2 py-4 sm:grid-cols-[1fr_1fr_auto] sm:items-center">
                  <div>
                    <p className="text-sm font-medium">{role.label}</p>
                    <p className="mt-0.5 text-xs uppercase text-muted-foreground">{role.code}</p>
                  </div>
                  <p className="font-mono text-sm text-muted-foreground">{role.model || '未配置'}</p>
                  <Badge variant={role.status === 'active' ? 'secondary' : 'outline'} className="w-fit font-normal">
                    {role.status === 'active' ? '运行中' : role.status === 'manual_only' ? '仅人工' : '未启用'}
                  </Badge>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-md border border-border p-5">
              <div className="flex items-center gap-2">
                <Route className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">当前编排策略</h2>
              </div>
              <p className="mt-3 text-2xl font-semibold">
                {policyData?.policy.mode === 'economy'
                  ? '省成本'
                  : policyData?.policy.mode === 'strict'
                    ? '严谨优先'
                    : '智能平衡'}
              </p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                本地规则先判断任务风险。普通任务直接完成，复杂任务最多校验一次，高风险任务进入严格复核。
              </p>
              <div className="mt-5 grid grid-cols-3 gap-px overflow-hidden rounded border border-border bg-border text-center">
                <div className="bg-background px-2 py-3">
                  <p className="text-lg font-semibold">{policyData?.policy.max_calls ?? 2}</p>
                  <p className="text-xs text-muted-foreground">最多调用</p>
                </div>
                <div className="bg-background px-2 py-3">
                  <p className="text-lg font-semibold">{policyData?.policy.max_verifications ?? 1}</p>
                  <p className="text-xs text-muted-foreground">最多校验</p>
                </div>
                <div className="bg-background px-2 py-3">
                  <p className="text-lg font-semibold">${policyData?.policy.max_task_cost_usd ?? 0.08}</p>
                  <p className="text-xs text-muted-foreground">成本上限</p>
                </div>
              </div>
            </div>

            <div className="rounded-md border border-border p-5">
              <h2 className="text-sm font-semibold">执行角色</h2>
              <div className="mt-3 space-y-3">
                {(policyWorkers || []).filter((worker) => worker.enabled).map((worker) => (
                  <div key={worker.code} className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{worker.label}</p>
                      <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{worker.capability}</p>
                    </div>
                    <Badge variant="outline" className="font-normal">最多 {worker.max_calls} 次</Badge>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="rounded-md border border-border p-5">
            <div className="flex items-center gap-2">
              <Play className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold">策略仿真</h2>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">不调用模型，先预览任务会如何被路由和限制。</p>
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <Input value={simulationQuery} onChange={(event) => setSimulationQuery(event.target.value)} />
              <Button variant="outline" onClick={handleSimulate} disabled={simulatePolicy.isPending}>
                {simulatePolicy.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                运行仿真
              </Button>
            </div>
            {simulationResult && (
              <div className="mt-4 grid gap-3 rounded-md bg-muted/45 p-4 sm:grid-cols-4">
                <div><p className="text-xs text-muted-foreground">风险</p><p className="mt-1 text-sm font-medium">{simulationResult.profile.risk_level}</p></div>
                <div><p className="text-xs text-muted-foreground">执行深度</p><p className="mt-1 text-sm font-medium">{simulationResult.profile.execution_depth}</p></div>
                <div><p className="text-xs text-muted-foreground">预计调用</p><p className="mt-1 text-sm font-medium">{simulationResult.estimated_calls} 次</p></div>
                <div><p className="text-xs text-muted-foreground">预计时延</p><p className="mt-1 text-sm font-medium">{simulationResult.estimated_latency_ms} ms</p></div>
              </div>
            )}
          </section>
        </TabsContent>

        {/* Models Tab */}
        <TabsContent value="models" className="mt-4">
          {modelsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
            </div>
          ) : !models || models.length === 0 ? (
            <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed">
              <Cpu className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium">暂无模型</h3>
              <p className="text-muted-foreground mb-6">添加您的第一个 LLM 模型</p>
              <Button variant="outline" onClick={handleOpenCreate}>
                <Plus className="w-4 h-4 mr-2" /> 新增模型
              </Button>
            </div>
          ) : (
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-muted/30">
                      <th className="text-left p-3 text-xs font-medium text-muted-foreground">模型名称</th>
                      <th className="text-left p-3 text-xs font-medium text-muted-foreground">厂商</th>
                      <th className="text-left p-3 text-xs font-medium text-muted-foreground">类型</th>
                      <th className="text-left p-3 text-xs font-medium text-muted-foreground">状态</th>
                      <th className="text-left p-3 text-xs font-medium text-muted-foreground">默认</th>
                      <th className="text-right p-3 text-xs font-medium text-muted-foreground">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.map((model) => (
                      <tr key={model.id} className="border-b last:border-b-0 hover:bg-muted/20 transition-colors">
                        <td className="p-3">
                          <div>
                            <p className="text-sm font-medium">{model.model_name}</p>
                            <p className="text-xs text-muted-foreground font-mono">{model.model_code}</p>
                          </div>
                        </td>
                        <td className="p-3">
                          <Badge variant="secondary" className="text-xs">
                            {MODEL_PROVIDER_NAMES[model.provider_type] || model.provider_type}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <Badge variant="outline" className="text-xs">
                            {model.model_type === 'chat' ? '对话' : '向量'}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <Switch
                            checked={model.is_active}
                            onCheckedChange={() => handleToggleActive(model)}
                          />
                        </td>
                        <td className="p-3">
                          {model.is_default && (
                            <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                          )}
                        </td>
                        <td className="p-3">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => handleTest(model.id)}
                              disabled={testingId === model.id}
                            >
                              {testingId === model.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <TestTube className="w-3.5 h-3.5" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => handleOpenEdit(model)}
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(model)}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </TabsContent>

        {/* Model Marketplace Tab */}
        <TabsContent value="marketplace" className="mt-4">
          <div className="space-y-4">
            {/* Header with stats */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="relative flex-1 min-w-[280px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    placeholder="搜索模型名称或 ID..."
                    value={marketSearch}
                    onChange={(e) => setMarketSearch(e.target.value)}
                  />
                </div>
                <Button variant="outline" size="icon" onClick={() => refetchMarket()} disabled={marketLoading}>
                  <RefreshCw className={cn('w-4 h-4', marketLoading && 'animate-spin')} />
                </Button>
              </div>
              {availableData && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>上游: {availableData.upstream_providers?.join(' + ')}</span>
                  <span>·</span>
                  <span>共 {availableData.upstream_total} 个模型</span>
                  <span>·</span>
                  <span>已添加 {availableData.already_added} 个</span>
                </div>
              )}
            </div>

            {/* Filter chips */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Type filters */}
              <Badge
                variant={!marketTypeFilter ? 'default' : 'outline'}
                className="cursor-pointer select-none"
                onClick={() => setMarketTypeFilter(undefined)}
              >
                全部
              </Badge>
              <Badge
                variant={marketTypeFilter === 'chat' ? 'default' : 'outline'}
                className="cursor-pointer select-none gap-1"
                onClick={() => setMarketTypeFilter(marketTypeFilter === 'chat' ? undefined : 'chat')}
              >
                <MessageSquare className="w-3 h-3" /> 对话模型
              </Badge>
              <Badge
                variant={marketTypeFilter === 'embedding' ? 'default' : 'outline'}
                className="cursor-pointer select-none gap-1"
                onClick={() => setMarketTypeFilter(marketTypeFilter === 'embedding' ? undefined : 'embedding')}
              >
                <Hash className="w-3 h-3" /> 向量模型
              </Badge>
              <Separator orientation="vertical" className="h-5 mx-1" />
              {/* Tag filters */}
              {allTags.map((tag) => (
                <Badge
                  key={tag}
                  variant={marketTagFilter === tag ? 'default' : 'outline'}
                  className={cn(
                    'cursor-pointer select-none text-xs',
                    marketTagFilter === tag ? '' : MODEL_TAG_COLORS[tag] || 'bg-muted'
                  )}
                  onClick={() => setMarketTagFilter(marketTagFilter === tag ? undefined : tag)}
                >
                  {tag}
                </Badge>
              ))}
            </div>

            {/* Model categories */}
            {marketLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-40 rounded-xl" />
                ))}
              </div>
            ) : !availableData?.categories?.length ? (
              <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed">
                <ShoppingBag className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium">无可用模型</h3>
                <p className="text-muted-foreground">未能从上游转发商获取到模型列表，请检查 API Key 配置</p>
              </div>
            ) : (
              <div className="space-y-8">
                {availableData.categories.map((category) => (
                  <div key={category.name}>
                    <h3 className="text-base font-semibold mb-3 flex items-center gap-2">
                      <span>{category.icon}</span> {category.name}
                      <Badge variant="secondary" className="text-xs font-normal">{category.models.length}</Badge>
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                      {category.models.map((model) => (
                        <Card
                          key={model.model_id}
                          className={cn(
                            'group relative overflow-hidden transition-all duration-200 hover:shadow-md hover:border-primary/30',
                            model.already_added && 'opacity-60'
                          )}
                        >
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1 min-w-0">
                                <h4 className="text-sm font-semibold truncate">{model.name}</h4>
                                <p className="text-xs text-muted-foreground font-mono truncate">{model.model_id}</p>
                              </div>
                              <Badge variant="secondary" className="text-[10px] shrink-0 ml-2">
                                {model.provider_label}
                              </Badge>
                            </div>

                            {/* Tags */}
                            {model.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mb-3">
                                {model.tags.map((tag) => (
                                  <span
                                    key={tag}
                                    className={cn(
                                      'inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded border',
                                      MODEL_TAG_COLORS[tag] || 'bg-muted text-muted-foreground'
                                    )}
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Specs */}
                            {model.has_metadata && (
                              <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground mb-3">
                                <div>
                                  <span className="block text-[10px] uppercase tracking-wider">上下文</span>
                                  <span className="font-medium text-foreground">{formatContextWindow(model.context_window)}</span>
                                </div>
                                <div>
                                  <span className="block text-[10px] uppercase tracking-wider">输入价格</span>
                                  <span className="font-medium text-foreground">${model.input_price_per_1m}/M</span>
                                </div>
                                <div>
                                  <span className="block text-[10px] uppercase tracking-wider">能力</span>
                                  <div className="flex gap-0.5">
                                    {model.supports_tools && (
                                      <span title="支持工具调用" className="text-emerald-500"><Wrench className="w-3 h-3" /></span>
                                    )}
                                    {model.supports_streaming && (
                                      <span title="支持流式输出" className="text-blue-500"><Zap className="w-3 h-3" /></span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Source */}
                            {model.available_from?.length > 0 && (
                              <p className="text-[10px] text-muted-foreground mb-3">
                                来源: {model.available_from.join(', ')}
                              </p>
                            )}

                            {/* Action */}
                            <div className="flex items-center justify-end">
                              {model.already_added ? (
                                <Badge variant="secondary" className="text-xs gap-1">
                                  <CheckCircle2 className="w-3 h-3" /> 已添加
                                </Badge>
                              ) : (
                                <Button
                                  size="sm"
                                  className="h-7 text-xs gap-1"
                                  onClick={() => setConfirmAddModel(model)}
                                >
                                  <Plus className="w-3 h-3" /> 一键添加
                                </Button>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* Schedule Rules Tab - 4-Tier Model Configuration */}
        <TabsContent value="rules" className="mt-4">
          <div className="space-y-4">
            {/* Header */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Settings2 className="w-4 h-4" />
                  历史模型调度规则
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  仅用于兼容旧配置。生产请求由统一执行策略控制，不会自动切换到高价模型。
                </p>
              </CardHeader>
            </Card>

            {rulesLoading || modelsLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-48 rounded-xl" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {MODEL_TIERS.map((tier) => {
                  const TierIcon = tier.icon;
                  const rule = getRuleForTier(tier.value);
                  const activeModels = models?.filter((m) => m.is_active && m.model_type === 'chat') || [];
                  const primaryModel = activeModels.find(
                    (m) => String(m.id) === rule?.primary_model
                  );

                  return (
                    <Card key={tier.value} className={cn('relative overflow-hidden', tier.bgColor)}>
                      <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <TierIcon className={cn('w-5 h-5', tier.color)} />
                            <CardTitle className="text-sm font-semibold">{tier.label}</CardTitle>
                          </div>
                          {rule && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-destructive hover:text-destructive"
                              onClick={() => handleDeleteTierRule(tier.value)}
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{tier.description}</p>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {/* Primary Model Select */}
                        <div className="space-y-1.5">
                          <Label className="text-xs font-medium">主模型</Label>
                          <Select
                            disabled
                            value={rule?.primary_model || ''}
                            onValueChange={(v) => handleSaveTierRule(tier.value, v, rule?.backup_model || '')}
                          >
                            <SelectTrigger className="h-8 text-xs bg-background">
                              <SelectValue placeholder="选择主模型..." />
                            </SelectTrigger>
                            <SelectContent>
                              {activeModels.map((m) => (
                                <SelectItem key={m.id} value={String(m.id)}>
                                  <span className="flex items-center gap-2">
                                    <span>{m.model_name}</span>
                                    <span className="text-muted-foreground font-mono text-[10px]">{m.model_code}</span>
                                  </span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Backup Model Select */}
                        <div className="space-y-1.5">
                          <Label className="text-xs font-medium">备用模型</Label>
                          <Select
                            disabled
                            value={rule?.backup_model || 'none'}
                            onValueChange={(v) =>
                              handleSaveTierRule(tier.value, rule?.primary_model || '', v === 'none' ? '' : v)
                            }
                          >
                            <SelectTrigger className="h-8 text-xs bg-background">
                              <SelectValue placeholder="选择备用模型（可选）..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">无</SelectItem>
                              {activeModels
                                .filter((m) => String(m.id) !== rule?.primary_model)
                                .map((m) => (
                                  <SelectItem key={m.id} value={String(m.id)}>
                                    <span className="flex items-center gap-2">
                                      <span>{m.model_name}</span>
                                      <span className="text-muted-foreground font-mono text-[10px]">{m.model_code}</span>
                                    </span>
                                  </SelectItem>
                                ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Status indicator */}
                        <div className="flex items-center gap-2 pt-1">
                          {rule ? (
                            <Badge variant="secondary" className="text-[10px] gap-1">
                              <CheckCircle2 className="w-3 h-3 text-green-500" />
                              已配置 · {primaryModel?.model_name || rule.primary_model}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[10px] gap-1 text-muted-foreground">
                              <Info className="w-3 h-3" />
                              使用系统默认
                            </Badge>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}

            {/* Additional custom rules table (non-tier rules) */}
            {rules && rules.filter((r) => !r.complexity_tier || !MODEL_TIERS.some((tier) => tier.value === r.complexity_tier)).length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">其他调度规则</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b bg-muted/30">
                          <th className="text-left p-2 text-xs font-medium text-muted-foreground">规则名</th>
                          <th className="text-left p-2 text-xs font-medium text-muted-foreground">场景</th>
                          <th className="text-left p-2 text-xs font-medium text-muted-foreground">Agent</th>
                          <th className="text-left p-2 text-xs font-medium text-muted-foreground">主模型</th>
                          <th className="text-left p-2 text-xs font-medium text-muted-foreground">备用</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rules
                          .filter((r) => !r.complexity_tier || !MODEL_TIERS.some((tier) => tier.value === r.complexity_tier))
                          .map((rule) => {
                            const allActiveModels = models?.filter((m) => m.is_active) || [];
                            return (
                            <tr key={rule.id} className="border-b last:border-b-0 text-xs">
                              <td className="p-2 truncate max-w-[150px]">{rule.rule_name}</td>
                              <td className="p-2 text-muted-foreground">{rule.scene_code}</td>
                              <td className="p-2 text-muted-foreground">{rule.agent_code || '*'}</td>
                              <td className="p-2">
                                <Select
                                  disabled
                                  value={rule.primary_model || ''}
                                  onValueChange={async (v) => {
                                    try {
                                      await updateRule.mutateAsync({
                                        id: rule.id,
                                        primary_model_id: v,
                                        backup_model_id: rule.backup_model || undefined,
                                      });
                                    } catch { /* toast handled */ }
                                  }}
                                >
                                  <SelectTrigger className="h-8 text-xs w-[220px] bg-background overflow-hidden">
                                    <SelectValue placeholder="选择模型..." />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {allActiveModels.map((m) => (
                                      <SelectItem key={m.id} value={String(m.id)}>
                                        <div className="flex items-center gap-2 truncate">
                                          <span className="truncate max-w-[100px] font-medium">{m.model_name}</span>
                                          <span className="text-muted-foreground font-mono text-[10px] shrink-0 truncate max-w-[80px]">{m.model_code}</span>
                                        </div>
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </td>
                              <td className="p-2">
                                <Select
                                  disabled
                                  value={rule.backup_model || 'none'}
                                  onValueChange={async (v) => {
                                    try {
                                      await updateRule.mutateAsync({
                                        id: rule.id,
                                        primary_model_id: rule.primary_model,
                                        backup_model_id: v === 'none' ? undefined : v,
                                      });
                                    } catch { /* toast handled */ }
                                  }}
                                >
                                  <SelectTrigger className="h-8 text-xs w-[220px] bg-background overflow-hidden">
                                    <SelectValue placeholder="选择备用..." />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="none">无备用模型</SelectItem>
                                    {allActiveModels
                                      .filter((m) => String(m.id) !== rule.primary_model)
                                      .map((m) => (
                                        <SelectItem key={m.id} value={String(m.id)}>
                                          <div className="flex items-center gap-2 truncate">
                                            <span className="truncate max-w-[100px] font-medium">{m.model_name}</span>
                                            <span className="text-muted-foreground font-mono text-[10px] shrink-0 truncate max-w-[80px]">{m.model_code}</span>
                                          </div>
                                        </SelectItem>
                                      ))}
                                  </SelectContent>
                                </Select>
                              </td>
                            </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Usage Stats Tab */}
        <TabsContent value="usage" className="mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Token 用量趋势</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={usageStats || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <Tooltip
                        contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="total_tokens" name="总Token" stroke={chartColors.primary} strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="input_tokens" name="输入Token" stroke={chartColors.info} strokeWidth={1.5} dot={false} />
                      <Line type="monotone" dataKey="output_tokens" name="输出Token" stroke={chartColors.success} strokeWidth={1.5} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">成本趋势</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={usageStats || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <YAxis tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                      <Tooltip
                        contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8 }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                      />
                      <Bar dataKey="cost" name="成本 (元)" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <ModelEditorDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        isEditing={isEditing}
        model={editModel}
        setModel={setEditModel}
        onSave={handleSave}
        onTest={handleTest}
        testingId={testingId}
        testResult={testResult}
        isSaving={createModel.isPending || updateModel.isPending}
      />
      <QuickAddModelDialog
        model={confirmAddModel}
        onOpenChange={(open) => !open && setConfirmAddModel(null)}
        onConfirm={handleQuickAdd}
        isPending={quickAdd.isPending}
      />
    </div>
  );
}
