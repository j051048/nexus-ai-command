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
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
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
  XCircle,
  Settings2,
  BarChart3,
  ShoppingBag,
  Search,
  Sparkles,
  ArrowRight,
  Info,
  Wrench,
  MessageSquare,
  Hash,
  RefreshCw,
  Rocket,
  Crown,
  Leaf,
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

// Provider 配置
const PROVIDERS = [
  { value: 'openai', label: 'OpenAI兼容' },
  { value: 'baidu', label: '百度文心' },
  { value: 'aliyun', label: '阿里通义' },
  { value: 'tencent', label: '腾讯混元' },
  { value: 'bytedance', label: '字节豆包' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'yi', label: '零一万物' },
  { value: 'anthropic', label: 'Anthropic' },
];

const PROVIDER_NAMES: Record<string, string> = Object.fromEntries(PROVIDERS.map(p => [p.value, p.label]));

// 4-Tier 智能路由配置
const TIERS = [
  { value: 'economy', label: '经济层', icon: Leaf, color: 'text-green-600', bgColor: 'bg-green-50 dark:bg-green-950/30', description: '简单问候、FAQ — 低成本高速响应' },
  { value: 'balanced', label: '均衡层', icon: Zap, color: 'text-blue-600', bgColor: 'bg-blue-50 dark:bg-blue-950/30', description: '单工具查询、状态查看 — 兼顾成本与能力' },
  { value: 'power', label: '强力层', icon: Rocket, color: 'text-orange-600', bgColor: 'bg-orange-50 dark:bg-orange-950/30', description: '多步分析、报告生成 — 高级推理能力' },
  { value: 'flagship', label: '旗舰层', icon: Crown, color: 'text-purple-600', bgColor: 'bg-purple-50 dark:bg-purple-950/30', description: '审批、财务操作 — 最高准确性保证' },
] as const;

const emptyModel: Partial<LLMModel> = {
  provider_type: 'openai',
  model_code: '',
  model_name: '',
  api_base_url: '',
  api_key: '',
  secret_key: '',
  model_id: '',
  model_type: 'chat',
  timeout_ms: 30000,
  max_tokens: 4096,
  context_window: 8192,
  supports_tools: true,
  supports_streaming: true,
  input_price: 0,
  output_price: 0,
  is_active: true,
  is_default: false,
};

// Tag 配色
const TAG_COLORS: Record<string, string> = {
  '推荐': 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  '高性价比': 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20',
  '多模态': 'bg-violet-500/15 text-violet-700 dark:text-violet-400 border-violet-500/20',
  '深度推理': 'bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/20',
  '推理': 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20',
  '国产': 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/20',
  '超长上下文': 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/20',
  '长上下文': 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/20',
  '经济': 'bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/20',
  '开源': 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-400 border-indigo-500/20',
  '向量': 'bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/20',
  '免费': 'bg-lime-500/15 text-lime-700 dark:text-lime-400 border-lime-500/20',
  '最新': 'bg-pink-500/15 text-pink-700 dark:text-pink-400 border-pink-500/20',
  '最强推理': 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20',
  '实验': 'bg-gray-500/15 text-gray-700 dark:text-gray-400 border-gray-500/20',
};

function formatContextWindow(n: number): string {
  if (!n) return '-';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1000) return `${Math.round(n / 1000)}K`;
  return String(n);
}

export default function LLMModelManagement() {
  const [activeTab, setActiveTab] = useState('models');
  const [editOpen, setEditOpen] = useState(false);
  const [editModel, setEditModel] = useState<Partial<LLMModel>>(emptyModel);
  const [isEditing, setIsEditing] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms: number } | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // Model marketplace state
  const [marketSearch, setMarketSearch] = useState('');
  const [marketTypeFilter, setMarketTypeFilter] = useState<string | undefined>(undefined);
  const [marketTagFilter, setMarketTagFilter] = useState<string | undefined>(undefined);
  const [confirmAddModel, setConfirmAddModel] = useState<AvailableModel | null>(null);

  // Queries
  const { data: models, isLoading: modelsLoading } = useLLMModels();
  const { data: rules, isLoading: rulesLoading } = useScheduleRules();
  const { data: usageStats } = useModelUsageStats('week');
  const { data: availableData, isLoading: marketLoading, refetch: refetchMarket } = useFetchAvailableModels({
    search: marketSearch || undefined,
    type: marketTypeFilter,
    tag: marketTagFilter,
  });

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
    setEditModel({ ...emptyModel });
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
          rule_name: `默认${TIERS.find((t) => t.value === tier)?.label || tier}规则`,
          scene_code: '*',
          agent_code: '*',
          primary_model_id: primaryModelId,
          backup_model_id: backupModelId || undefined,
          complexity_tier: tier,
          priority: TIERS.findIndex((t) => t.value === tier),
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

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">模型管理</h1>
          <p className="text-muted-foreground">管理 LLM 模型配置、调度规则与用量监控</p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="w-4 h-4 mr-2" />
          新增模型
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="models" className="gap-1.5">
            <Cpu className="w-3.5 h-3.5" /> 模型列表
          </TabsTrigger>
          <TabsTrigger value="marketplace" className="gap-1.5">
            <ShoppingBag className="w-3.5 h-3.5" /> 模型市场
          </TabsTrigger>
          <TabsTrigger value="rules" className="gap-1.5">
            <Settings2 className="w-3.5 h-3.5" /> 调度规则
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-1.5">
            <BarChart3 className="w-3.5 h-3.5" /> 用量统计
          </TabsTrigger>
        </TabsList>

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
                            {PROVIDER_NAMES[model.provider_type] || model.provider_type}
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
                    marketTagFilter === tag ? '' : TAG_COLORS[tag] || 'bg-muted'
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
                                      TAG_COLORS[tag] || 'bg-muted text-muted-foreground'
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
                  智能模型路由配置
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  为不同复杂度的查询配置专用模型。系统根据用户问题自动匹配合适的模型层级，选择即保存。
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
                {TIERS.map((tier) => {
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
            {rules && rules.filter((r) => !r.complexity_tier || !TIERS.some(t => t.value === r.complexity_tier)).length > 0 && (
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
                          .filter((r) => !r.complexity_tier || !TIERS.some(t => t.value === r.complexity_tier))
                          .map((rule) => {
                            const allActiveModels = models?.filter((m) => m.is_active) || [];
                            return (
                            <tr key={rule.id} className="border-b last:border-b-0 text-xs">
                              <td className="p-2 truncate max-w-[150px]">{rule.rule_name}</td>
                              <td className="p-2 text-muted-foreground">{rule.scene_code}</td>
                              <td className="p-2 text-muted-foreground">{rule.agent_code || '*'}</td>
                              <td className="p-2">
                                <Select
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

      {/* Create/Edit Model Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle>{isEditing ? '编辑模型' : '新增模型'}</DialogTitle>
            <DialogDescription>配置 LLM 模型的接入参数和能力选项</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh] pr-4">
            <div className="space-y-4 py-2">
              {/* Provider */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>模型厂商</Label>
                  <Select
                    value={editModel.provider_type || 'openai'}
                    onValueChange={(v) => setEditModel({ ...editModel, provider_type: v })}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PROVIDERS.map(p => (
                        <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>模型类型</Label>
                  <Select
                    value={editModel.model_type || 'chat'}
                    onValueChange={(v) => setEditModel({ ...editModel, model_type: v as 'chat' | 'embedding' })}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="chat">对话模型</SelectItem>
                      <SelectItem value="embedding">向量模型</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Code & Name */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>模型编码</Label>
                  <Input
                    placeholder="例如: gpt-4o"
                    value={editModel.model_code || ''}
                    onChange={(e) => setEditModel({ ...editModel, model_code: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>模型名称</Label>
                  <Input
                    placeholder="例如: GPT-4o"
                    value={editModel.model_name || ''}
                    onChange={(e) => setEditModel({ ...editModel, model_name: e.target.value })}
                  />
                </div>
              </div>

              {/* API Configuration */}
              <div className="space-y-2">
                <Label>API Base URL</Label>
                <Input
                  placeholder="https://api.openai.com/v1"
                  value={editModel.api_base_url || ''}
                  onChange={(e) => setEditModel({ ...editModel, api_base_url: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>API Key</Label>
                  <Input
                    type="password"
                    placeholder="sk-..."
                    value={editModel.api_key || ''}
                    onChange={(e) => setEditModel({ ...editModel, api_key: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Secret Key（可选）</Label>
                  <Input
                    type="password"
                    placeholder="百度等平台需要"
                    value={editModel.secret_key || ''}
                    onChange={(e) => setEditModel({ ...editModel, secret_key: e.target.value })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Model ID</Label>
                <Input
                  placeholder="模型标识符"
                  value={editModel.model_id || ''}
                  onChange={(e) => setEditModel({ ...editModel, model_id: e.target.value })}
                />
              </div>

              {/* Performance Parameters */}
              <Separator />
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>超时时间 (ms)</Label>
                  <Input
                    type="number"
                    value={editModel.timeout_ms || 30000}
                    onChange={(e) => setEditModel({ ...editModel, timeout_ms: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>最大Token</Label>
                  <Input
                    type="number"
                    value={editModel.max_tokens || 4096}
                    onChange={(e) => setEditModel({ ...editModel, max_tokens: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>上下文窗口</Label>
                  <Input
                    type="number"
                    value={editModel.context_window || 8192}
                    onChange={(e) => setEditModel({ ...editModel, context_window: Number(e.target.value) })}
                  />
                </div>
              </div>

              {/* Capabilities */}
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="supports_tools"
                    checked={editModel.supports_tools ?? true}
                    onCheckedChange={(checked) => setEditModel({ ...editModel, supports_tools: !!checked })}
                  />
                  <Label htmlFor="supports_tools" className="text-sm">支持工具调用</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="supports_streaming"
                    checked={editModel.supports_streaming ?? true}
                    onCheckedChange={(checked) => setEditModel({ ...editModel, supports_streaming: !!checked })}
                  />
                  <Label htmlFor="supports_streaming" className="text-sm">支持流式输出</Label>
                </div>
              </div>

              {/* Pricing */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>输入价格 (元/千Token)</Label>
                  <Input
                    type="number"
                    step="0.001"
                    value={editModel.input_price || 0}
                    onChange={(e) => setEditModel({ ...editModel, input_price: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>输出价格 (元/千Token)</Label>
                  <Input
                    type="number"
                    step="0.001"
                    value={editModel.output_price || 0}
                    onChange={(e) => setEditModel({ ...editModel, output_price: Number(e.target.value) })}
                  />
                </div>
              </div>

              {/* Test Result */}
              {isEditing && editModel.id && (
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => editModel.id && handleTest(editModel.id)}
                    disabled={testingId === editModel.id}
                  >
                    {testingId === editModel.id ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <TestTube className="w-4 h-4 mr-2" />
                    )}
                    测试连通性
                  </Button>
                  {testResult && (
                    <span className={cn("text-sm flex items-center gap-1", testResult.success ? "text-green-600" : "text-red-600")}>
                      {testResult.success ? (
                        <><CheckCircle2 className="w-4 h-4" /> 连通成功 ({testResult.latency_ms}ms)</>
                      ) : (
                        <><XCircle className="w-4 h-4" /> 连通失败</>
                      )}
                    </span>
                  )}
                </div>
              )}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>取消</Button>
            <Button
              onClick={handleSave}
              disabled={createModel.isPending || updateModel.isPending}
            >
              {(createModel.isPending || updateModel.isPending) && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Quick Add Confirmation Dialog */}
      <Dialog open={!!confirmAddModel} onOpenChange={(open) => !open && setConfirmAddModel(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              一键添加模型
            </DialogTitle>
            <DialogDescription>
              以下参数已从知识库自动预填充，确认后即可添加到您的模型列表
            </DialogDescription>
          </DialogHeader>
          {confirmAddModel && (
            <div className="space-y-3 py-2">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-xs text-muted-foreground block">模型名称</span>
                  <span className="font-medium">{confirmAddModel.name}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">模型 ID</span>
                  <span className="font-mono text-xs">{confirmAddModel.model_id}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">厂商</span>
                  <span>{confirmAddModel.provider_label}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">类型</span>
                  <span>{confirmAddModel.type === 'chat' ? '对话模型' : '向量模型'}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">上下文窗口</span>
                  <span>{formatContextWindow(confirmAddModel.context_window)}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">最大输出</span>
                  <span>{formatContextWindow(confirmAddModel.max_tokens)}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">输入价格</span>
                  <span>${confirmAddModel.input_price_per_1m}/M tokens</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">输出价格</span>
                  <span>${confirmAddModel.output_price_per_1m}/M tokens</span>
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                {confirmAddModel.supports_tools && (
                  <span className="flex items-center gap-1"><Wrench className="w-3 h-3 text-emerald-500" /> 工具调用</span>
                )}
                {confirmAddModel.supports_streaming && (
                  <span className="flex items-center gap-1"><Zap className="w-3 h-3 text-blue-500" /> 流式输出</span>
                )}
              </div>
              {!confirmAddModel.has_metadata && (
                <div className="flex items-start gap-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 rounded-lg p-3">
                  <Info className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>该模型不在知识库中，部分参数为默认值，添加后可能需要手动调整。</span>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmAddModel(null)}>取消</Button>
            <Button onClick={handleQuickAdd} disabled={quickAdd.isPending}>
              {quickAdd.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              确认添加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
