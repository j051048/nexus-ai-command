/**
 * LLM 模型管理页面
 * 模型CRUD + 连通性测试 + 调度规则 + 用量统计
 */

import React, { useState } from 'react';
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
  useModelUsageStats,
  type LLMModel,
  type ScheduleRule,
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

export default function LLMModelManagement() {
  const [activeTab, setActiveTab] = useState('models');
  const [editOpen, setEditOpen] = useState(false);
  const [editModel, setEditModel] = useState<Partial<LLMModel>>(emptyModel);
  const [isEditing, setIsEditing] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms: number } | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // Queries
  const { data: models, isLoading: modelsLoading } = useLLMModels();
  const { data: rules, isLoading: rulesLoading } = useScheduleRules();
  const { data: usageStats } = useModelUsageStats('week');

  // Mutations
  const createModel = useCreateLLMModel();
  const updateModel = useUpdateLLMModel();
  const deleteModel = useDeleteLLMModel();
  const testModel = useTestLLMModel();

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

        {/* Schedule Rules Tab */}
        <TabsContent value="rules" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">调度规则配置</CardTitle>
            </CardHeader>
            <CardContent>
              {rulesLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : !rules || rules.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  暂无调度规则，系统将使用默认模型
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/30">
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">场景</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">Agent</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">主模型</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">备用模型</th>
                        <th className="text-left p-3 text-xs font-medium text-muted-foreground">策略</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rules.map((rule) => (
                        <tr key={rule.id} className="border-b last:border-b-0">
                          <td className="p-3 text-sm">{rule.scene_code}</td>
                          <td className="p-3 text-sm">{rule.agent_code}</td>
                          <td className="p-3 text-sm font-mono text-xs">{rule.primary_model}</td>
                          <td className="p-3 text-sm font-mono text-xs">{rule.backup_model || '-'}</td>
                          <td className="p-3">
                            <Badge variant="outline" className="text-xs">{rule.strategy}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
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
    </div>
  );
}
