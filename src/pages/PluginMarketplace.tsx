/**
 * 插件/扩展市场
 * 浏览、安装、配置和管理组织插件
 */

import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import {
  Puzzle,
  Download,
  Trash2,
  Settings,
  Database,
  MessageCircle,
  Mail,
  Shield,
  Bell,
  BarChart3,
  Server,
  ShieldCheck,
  Star,
  Check,
  Search,
  Package,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';

// 类别配置
const CATEGORIES = [
  { value: 'all', label: '全部', icon: Package },
  { value: 'erp', label: 'ERP', icon: Database },
  { value: 'notification', label: '通知', icon: Bell },
  { value: 'productivity', label: '生产力', icon: BarChart3 },
  { value: 'security', label: '安全', icon: Shield },
];

// 图标映射
const ICON_MAP: Record<string, React.ElementType> = {
  'database': Database,
  'message-circle': MessageCircle,
  'mail': Mail,
  'shield': Shield,
  'bell': Bell,
  'bar-chart-3': BarChart3,
  'server': Server,
  'shield-check': ShieldCheck,
};

// 分类颜色
const CATEGORY_COLORS: Record<string, string> = {
  erp: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  notification: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  productivity: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  security: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
};

// 分类中文名
const CATEGORY_LABELS: Record<string, string> = {
  erp: 'ERP',
  notification: '通知',
  productivity: '生产力',
  security: '安全',
};

interface PluginConfigSchema {
  [key: string]: {
    type: string;
    label: string;
    required: boolean;
    placeholder?: string;
  };
}

interface Plugin {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  icon: string;
  is_builtin: boolean;
  author: string;
  downloads: number;
  rating: number;
  config_schema: PluginConfigSchema;
  installed?: boolean;
  config?: Record<string, string>;
  is_active?: boolean;
  installed_at?: string;
}

// 内置插件数据（前端降级使用）
const BUILTIN_PLUGINS: Plugin[] = [
  {
    id: 'plugin_kingdee',
    name: '金蝶 ERP 集成',
    description: '连接金蝶 ERP 系统，同步进销存和财务数据',
    category: 'erp',
    version: '1.0.0',
    icon: 'database',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 1280,
    rating: 4.5,
    config_schema: {
      api_url: { type: 'text', label: 'API 地址', required: true, placeholder: 'https://your-kingdee-instance.com/api' },
      api_key: { type: 'password', label: 'API 密钥', required: true, placeholder: '输入 API 密钥' },
    },
  },
  {
    id: 'plugin_wecom_bot',
    name: '企业微信机器人',
    description: '通过企微群机器人推送通知和报告',
    category: 'notification',
    version: '1.0.0',
    icon: 'message-circle',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 3560,
    rating: 4.8,
    config_schema: {
      webhook_url: { type: 'text', label: 'Webhook 地址', required: true, placeholder: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx' },
    },
  },
  {
    id: 'plugin_email_digest',
    name: '邮件日报摘要',
    description: '每日自动发送工作摘要邮件',
    category: 'productivity',
    version: '1.0.0',
    icon: 'mail',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 2100,
    rating: 4.3,
    config_schema: {
      recipients: { type: 'text', label: '收件人', required: true, placeholder: '多个邮箱以逗号分隔' },
      send_time: { type: 'text', label: '发送时间', required: false, placeholder: '18:00 (默认)' },
    },
  },
  {
    id: 'plugin_data_backup',
    name: '数据自动备份',
    description: '定期自动备份组织数据到指定存储',
    category: 'security',
    version: '1.0.0',
    icon: 'shield',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 980,
    rating: 4.6,
    config_schema: {},
  },
  {
    id: 'plugin_dingtalk',
    name: '钉钉集成',
    description: '连接钉钉工作台，同步审批和通知',
    category: 'notification',
    version: '1.0.0',
    icon: 'bell',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 2800,
    rating: 4.4,
    config_schema: {
      app_key: { type: 'text', label: 'AppKey', required: true, placeholder: '钉钉应用 AppKey' },
      app_secret: { type: 'password', label: 'AppSecret', required: true, placeholder: '钉钉应用 AppSecret' },
    },
  },
  {
    id: 'plugin_ai_report',
    name: 'AI 智能报表',
    description: '自动生成周报、月报和数据分析报告',
    category: 'productivity',
    version: '1.0.0',
    icon: 'bar-chart-3',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 1750,
    rating: 4.7,
    config_schema: {
      report_type: { type: 'text', label: '报表类型', required: false, placeholder: 'weekly/monthly' },
    },
  },
  {
    id: 'plugin_yonyou',
    name: '用友 U8 集成',
    description: '对接用友 U8 财务与供应链管理系统',
    category: 'erp',
    version: '1.0.0',
    icon: 'server',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 890,
    rating: 4.2,
    config_schema: {
      server_url: { type: 'text', label: '服务器地址', required: true, placeholder: 'https://u8-server.example.com' },
      token: { type: 'password', label: '访问令牌', required: true, placeholder: '输入访问令牌' },
    },
  },
  {
    id: 'plugin_compliance_check',
    name: '合规审查助手',
    description: '自动检查文档和流程的合规性',
    category: 'security',
    version: '1.0.0',
    icon: 'shield-check',
    is_builtin: true,
    author: 'Nexus 官方',
    downloads: 670,
    rating: 4.1,
    config_schema: {},
  },
];

export function PluginMarketplace() {
  const [plugins, setPlugins] = useState<Plugin[]>(BUILTIN_PLUGINS);
  const [installedSet, setInstalledSet] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState('all');
  const [search, setSearch] = useState('');
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [installing, setInstalling] = useState<string | null>(null);

  // 筛选插件
  const filteredPlugins = plugins.filter((p) => {
    const matchCategory = activeTab === 'all' || activeTab === 'installed' || p.category === activeTab;
    const matchSearch = !search || p.name.includes(search) || p.description.includes(search);
    const matchInstalled = activeTab !== 'installed' || installedSet.has(p.id);
    return matchCategory && matchSearch && matchInstalled;
  });

  const handleInstall = (plugin: Plugin) => {
    const schema = plugin.config_schema || {};
    const hasConfig = Object.keys(schema).length > 0;

    if (hasConfig) {
      setSelectedPlugin(plugin);
      setConfigValues(plugin.config || {});
      setConfigDialogOpen(true);
    } else {
      doInstall(plugin, {});
    }
  };

  const doInstall = async (plugin: Plugin, config: Record<string, string>) => {
    setInstalling(plugin.id);
    // 模拟安装延迟
    await new Promise((r) => setTimeout(r, 800));
    setInstalledSet((prev) => new Set([...prev, plugin.id]));
    setPlugins((prev) =>
      prev.map((p) => (p.id === plugin.id ? { ...p, installed: true, config } : p))
    );
    setInstalling(null);
    setConfigDialogOpen(false);
    toast.success(`${plugin.name} 安装成功`);
  };

  const handleUninstall = async (plugin: Plugin) => {
    setInstalling(plugin.id);
    await new Promise((r) => setTimeout(r, 500));
    setInstalledSet((prev) => {
      const next = new Set(prev);
      next.delete(plugin.id);
      return next;
    });
    setPlugins((prev) =>
      prev.map((p) => (p.id === plugin.id ? { ...p, installed: false, config: {} } : p))
    );
    setInstalling(null);
    toast.success(`${plugin.name} 已卸载`);
  };

  const handleConfigSave = () => {
    if (!selectedPlugin) return;
    const schema = selectedPlugin.config_schema || {};
    for (const [key, field] of Object.entries(schema)) {
      if (field.required && !configValues[key]) {
        toast.error(`请填写 ${field.label}`);
        return;
      }
    }
    if (installedSet.has(selectedPlugin.id)) {
      // 更新配置
      setPlugins((prev) =>
        prev.map((p) =>
          p.id === selectedPlugin.id ? { ...p, config: { ...configValues } } : p
        )
      );
      setConfigDialogOpen(false);
      toast.success('配置已更新');
    } else {
      doInstall(selectedPlugin, { ...configValues });
    }
  };

  const openConfig = (plugin: Plugin) => {
    setSelectedPlugin(plugin);
    setConfigValues(plugin.config || {});
    setConfigDialogOpen(true);
  };

  const renderStars = (rating: number) => {
    const full = Math.floor(rating);
    const half = rating - full >= 0.5;
    return (
      <span className="flex items-center gap-0.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star
            key={i}
            className={cn(
              'h-3 w-3',
              i < full
                ? 'fill-yellow-400 text-yellow-400'
                : i === full && half
                  ? 'fill-yellow-400/50 text-yellow-400'
                  : 'text-gray-300 dark:text-gray-600'
            )}
          />
        ))}
        <span className="ml-1 text-xs text-muted-foreground">{rating}</span>
      </span>
    );
  };

  const PluginCard = ({ plugin }: { plugin: Plugin }) => {
    const IconComp = ICON_MAP[plugin.icon] || Package;
    const isInstalled = installedSet.has(plugin.id);
    const isLoading = installing === plugin.id;

    return (
      <Card className="relative group hover:shadow-md transition-shadow">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={cn(
                'p-2.5 rounded-lg',
                CATEGORY_COLORS[plugin.category] || 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
              )}>
                <IconComp className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-sm font-semibold">{plugin.name}</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">{plugin.author}</p>
              </div>
            </div>
            <Badge variant="outline" className="text-[10px]">
              v{plugin.version}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pt-0 space-y-3">
          <CardDescription className="text-xs leading-relaxed line-clamp-2">
            {plugin.description}
          </CardDescription>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {renderStars(plugin.rating)}
              <span className="text-xs text-muted-foreground">
                <Download className="inline h-3 w-3 mr-0.5" />
                {plugin.downloads}
              </span>
            </div>
            <Badge className={cn('text-[10px]', CATEGORY_COLORS[plugin.category])}>
              {CATEGORY_LABELS[plugin.category] || plugin.category}
            </Badge>
          </div>

          <div className="flex items-center gap-2 pt-1">
            {isInstalled ? (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1 text-xs h-8"
                  onClick={() => openConfig(plugin)}
                  disabled={Object.keys(plugin.config_schema || {}).length === 0}
                >
                  <Settings className="h-3 w-3 mr-1" />
                  配置
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs h-8 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                  onClick={() => handleUninstall(plugin)}
                  disabled={isLoading}
                >
                  {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                className="flex-1 text-xs h-8"
                onClick={() => handleInstall(plugin)}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <Download className="h-3 w-3 mr-1" />
                )}
                安装
              </Button>
            )}
          </div>

          {isInstalled && (
            <div className="absolute top-2 right-2">
              <div className="flex items-center gap-1 text-green-600 dark:text-green-400">
                <Check className="h-3.5 w-3.5" />
                <span className="text-[10px] font-medium">已安装</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Puzzle className="h-6 w-6 text-primary" />
          插件市场
        </h1>
        <p className="text-muted-foreground mt-1">
          浏览和安装插件，扩展系统功能
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Package className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{plugins.length}</p>
              <p className="text-xs text-muted-foreground">可用插件</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900">
              <Check className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{installedSet.size}</p>
              <p className="text-xs text-muted-foreground">已安装</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900">
              <Star className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                {(plugins.reduce((acc, p) => acc + p.rating, 0) / plugins.length).toFixed(1)}
              </p>
              <p className="text-xs text-muted-foreground">平均评分</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 搜索和分类 */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索插件..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {CATEGORIES.map((cat) => (
            <TabsTrigger key={cat.value} value={cat.value} className="gap-1.5">
              <cat.icon className="h-3.5 w-3.5" />
              {cat.label}
            </TabsTrigger>
          ))}
          <TabsTrigger value="installed" className="gap-1.5">
            <Check className="h-3.5 w-3.5" />
            已安装 ({installedSet.size})
          </TabsTrigger>
        </TabsList>

        {/* 插件网格 - 所有 tab 共用同一个渲染 */}
        <div className="mt-6">
          {filteredPlugins.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <Package className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p>
                {activeTab === 'installed' ? '暂无已安装的插件' : '没有找到匹配的插件'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredPlugins.map((plugin) => (
                <PluginCard key={plugin.id} plugin={plugin} />
              ))}
            </div>
          )}
        </div>
      </Tabs>

      {/* 配置弹窗 */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              {selectedPlugin ? (installedSet.has(selectedPlugin.id) ? '编辑配置' : '安装配置') : '插件配置'}
            </DialogTitle>
            <DialogDescription>
              {selectedPlugin?.name} - {selectedPlugin?.description}
            </DialogDescription>
          </DialogHeader>

          {selectedPlugin && (
            <div className="space-y-4 py-2">
              {Object.entries(selectedPlugin.config_schema || {}).map(([key, field]) => (
                <div key={key} className="space-y-1.5">
                  <Label className="text-sm">
                    {field.label}
                    {field.required && <span className="text-red-500 ml-0.5">*</span>}
                  </Label>
                  <Input
                    type={field.type === 'password' ? 'password' : 'text'}
                    placeholder={field.placeholder}
                    value={configValues[key] || ''}
                    onChange={(e) =>
                      setConfigValues((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}

              {Object.keys(selectedPlugin.config_schema || {}).length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  此插件无需配置
                </p>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleConfigSave} disabled={installing !== null}>
              {installing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
              {selectedPlugin && installedSet.has(selectedPlugin.id) ? '保存配置' : '确认安装'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default PluginMarketplace;
