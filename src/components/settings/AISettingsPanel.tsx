import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAISettings, useSaveAISettings, useTestAIConnection, DEFAULT_MODELS } from '@/hooks/useAISettings';
import { useAuth } from '@/components/auth/AuthContext';
import { toast } from 'sonner';
import {
  Settings,
  Key,
  Globe,
  Bot,
  Save,
  TestTube2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Terminal,
  Shield
} from 'lucide-react';
import { UsageStats } from './UsageStats';
import { OrgPolicyEditor } from './OrgPolicyEditor';

interface LogEntry {
  timestamp: Date;
  type: 'info' | 'success' | 'error' | 'warning';
  message: string;
}

export function AISettingsPanel() {
  const { data: settings, isLoading } = useAISettings();
  const saveSettings = useSaveAISettings();
  const testConnection = useTestAIConnection();
  const { profile, loading: authLoading } = useAuth();

  const [baseUrl, setBaseUrl] = useState('https://api.apiyi.com/v1');
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('gemini-3-flash-preview');
  const [customModel, setCustomModel] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // Load saved settings
  useEffect(() => {
    if (settings) {
      setBaseUrl(settings.base_url || 'https://api.apiyi.com/v1');
      setApiKey(settings.api_key || '');

      const isCustom = !DEFAULT_MODELS.some(m => m.value === settings.model);
      if (isCustom && settings.model) {
        setSelectedModel('custom');
        setCustomModel(settings.model);
        setShowCustomInput(true);
      } else {
        setSelectedModel(settings.model || 'gemini-3-flash-preview');
      }
    }
  }, [settings]);

  const addLog = (type: LogEntry['type'], message: string) => {
    setLogs(prev => [...prev, { timestamp: new Date(), type, message }]);
  };

  const getEffectiveModel = () => {
    return showCustomInput ? customModel : selectedModel;
  };

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    if (value === 'custom') {
      setShowCustomInput(true);
    } else {
      setShowCustomInput(false);
      setCustomModel('');
    }
  };

  const handleSave = async () => {
    const model = getEffectiveModel();
    if (!model) {
      toast.error('请选择或输入模型名称');
      return;
    }

    addLog('info', '正在保存配置...');

    try {
      await saveSettings.mutateAsync({
        base_url: baseUrl,
        api_key: apiKey || null,
        model,
      });
      addLog('success', '配置保存成功！');
      toast.success('AI 配置已保存');
    } catch (error) {
      const message = error instanceof Error ? error.message : (typeof error === 'string' ? error : '保存失败');
      addLog('error', `保存失败: ${message}`);
      toast.error('保存失败: ' + message);
    }
  };

  const handleTest = async () => {
    const model = getEffectiveModel();
    if (!baseUrl) {
      toast.error('请输入 Base URL');
      addLog('error', '测试失败: Base URL 不能为空');
      return;
    }
    if (!apiKey) {
      toast.error('请输入 API Key');
      addLog('error', '测试失败: API Key 不能为空');
      return;
    }
    if (!model) {
      toast.error('请选择或输入模型');
      addLog('error', '测试失败: 模型不能为空');
      return;
    }

    addLog('info', `正在测试连接... (${model})`);
    addLog('info', `Base URL: ${baseUrl}`);

    try {
      const result = await testConnection.mutateAsync({
        base_url: baseUrl,
        api_key: apiKey,
        model,
      });
      addLog('success', `连接成功! AI 响应: ${result}`);
      toast.success('连接测试成功！');
    } catch (error) {
      const message = error instanceof Error ? error.message : '连接失败';
      addLog('error', `连接失败: ${message}`);
      toast.error('连接测试失败: ' + message);
    }
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const getLogIcon = (type: LogEntry['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-success" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-destructive" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-warning" />;
      default:
        return <Terminal className="w-4 h-4 text-muted-foreground" />;
    }
  };

  if (isLoading || authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto p-4 sm:p-6">
      <div className="flex items-center gap-3">
        <div className="p-3 bg-primary/10 rounded-xl">
          <Settings className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">设置中心</h1>
          <p className="text-muted-foreground">管理 AI 配置和组织行为准则</p>
        </div>
      </div>

      <Tabs defaultValue="ai-config">
        <TabsList>
          <TabsTrigger value="ai-config" className="gap-1.5">
            <Bot className="w-4 h-4" />
            AI 配置
          </TabsTrigger>
          <TabsTrigger value="org-policy" className="gap-1.5">
            <Shield className="w-4 h-4" />
            组织行为准则
          </TabsTrigger>
        </TabsList>

        <TabsContent value="ai-config" className="space-y-6 mt-4">
        <div className="grid gap-6 lg:grid-cols-2">
        {/* Configuration Card */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="w-5 h-5" />
              API 配置
            </CardTitle>
            <CardDescription>
              设置 AI 服务的接口地址和认证信息
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Base URL */}
            <div className="space-y-2">
              <Label htmlFor="base-url" className="flex items-center gap-2">
                <Globe className="w-4 h-4" />
                Base URL
              </Label>
              <Input
                id="base-url"
                placeholder="https://api.apiyi.com/v1"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                OpenAI 兼容的 API 地址（如 https://api.apiyi.com/v1），系统会自动拼接 /chat/completions
              </p>
            </div>

            {/* API Key */}
            <div className="space-y-2">
              <Label htmlFor="api-key" className="flex items-center gap-2">
                <Key className="w-4 h-4" />
                API Key
              </Label>
              <Input
                id="api-key"
                type="password"
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                API 密钥将安全存储在数据库中
              </p>
            </div>

            {/* Model Selection */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Bot className="w-4 h-4" />
                模型选择
              </Label>
              <Select value={selectedModel} onValueChange={handleModelChange}>
                <SelectTrigger>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {DEFAULT_MODELS.map((model) => (
                    <SelectItem key={model.value} value={model.value}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Custom Model Input */}
            {showCustomInput && (
              <div className="space-y-2">
                <Label htmlFor="custom-model">自定义模型名称</Label>
                <Input
                  id="custom-model"
                  placeholder="例如: gpt-4-turbo-2024"
                  value={customModel}
                  onChange={(e) => setCustomModel(e.target.value)}
                />
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4">
              <Button
                onClick={handleSave}
                disabled={saveSettings.isPending || !profile}
                className="flex-1"
              >
                {saveSettings.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                保存配置
              </Button>
              <Button
                variant="outline"
                onClick={handleTest}
                disabled={testConnection.isPending}
                className="flex-1"
              >
                {testConnection.isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <TestTube2 className="w-4 h-4 mr-2" />
                )}
                测试连接
              </Button>
            </div>
            {!profile && (
              <p className="text-xs text-destructive mt-2">
                无法获取用户组织信息，请尝试退出后重新登录
              </p>
            )}
          </CardContent>
        </Card>

        {/* Log Viewer Card */}
        <Card className="border-border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Terminal className="w-5 h-5" />
                对话日志
              </CardTitle>
              <CardDescription>
                查看 API 请求和响应日志
              </CardDescription>
            </div>
            <Button variant="ghost" size="sm" onClick={clearLogs}>
              清空
            </Button>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[320px] rounded-lg border border-border bg-muted/30 p-3">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <Terminal className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-sm">暂无日志</p>
                  <p className="text-xs">测试连接后日志将在此显示</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {logs.map((log, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-2 text-sm font-mono"
                    >
                      {getLogIcon(log.type)}
                      <span className="text-muted-foreground text-xs">
                        [{log.timestamp.toLocaleTimeString()}]
                      </span>
                      <span
                        className={
                          log.type === 'error'
                            ? 'text-destructive'
                            : log.type === 'success'
                              ? 'text-success'
                              : log.type === 'warning'
                                ? 'text-warning'
                                : 'text-foreground'
                        }
                      >
                        {log.message}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>

            {/* P1: Usage Statistics */}
      <div className="grid gap-6 lg:grid-cols-2">
        <UsageStats />
        
        {/* Quick Tips */}
        <Card className="border-border">
          <CardHeader>
            <CardTitle>使用提示</CardTitle>
            <CardDescription>优化 AI 使用成本的建议</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-success mt-0.5" />
              <p className="text-sm">使用更简洁的提示词可以减少 token 消耗</p>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-success mt-0.5" />
              <p className="text-sm">对于简单任务，可以选择更经济的模型</p>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-success mt-0.5" />
              <p className="text-sm">避免在对话中重复发送相同的上下文</p>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-success mt-0.5" />
              <p className="text-sm">利用知识库工具减少重复查询</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Info Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="border-border bg-muted/30">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="bg-primary/10">
                默认
              </Badge>
              <div>
                <p className="text-sm font-medium">ZHZ-Tech AI Gateway</p>
                <p className="text-xs text-muted-foreground">内置 API，无需额外配置</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-border bg-muted/30">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="bg-success/10 text-success">
                支持
              </Badge>
              <div>
                <p className="text-sm font-medium">OpenAI 兼容 API</p>
                <p className="text-xs text-muted-foreground">支持所有兼容接口</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-border bg-muted/30">
          <CardContent className="pt-4">
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="bg-warning/10 text-warning">
                提示
              </Badge>
              <div>
                <p className="text-sm font-medium">安全存储</p>
                <p className="text-xs text-muted-foreground">API Key 加密保存</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
        </TabsContent>

        <TabsContent value="org-policy" className="mt-4">
          <OrgPolicyEditor />
        </TabsContent>
      </Tabs>
    </div>
  );
}
