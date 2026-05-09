import React, { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bell,
  Check,
  Database,
  Download,
  Loader2,
  Mail,
  MessageCircle,
  Package,
  Puzzle,
  Search,
  Server,
  Settings,
  Shield,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { aiClient } from "@/api/aiClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { value: "all", label: "全部", icon: Package },
  { value: "erp", label: "ERP", icon: Database },
  { value: "notification", label: "通知", icon: Bell },
  { value: "productivity", label: "生产力", icon: BarChart3 },
  { value: "security", label: "安全", icon: Shield },
  { value: "installed", label: "已安装", icon: Check },
];

const ICON_MAP: Record<string, React.ElementType> = {
  "bar-chart-3": BarChart3,
  bell: Bell,
  database: Database,
  mail: Mail,
  "message-circle": MessageCircle,
  server: Server,
  shield: Shield,
  "shield-check": ShieldCheck,
};

const CATEGORY_COLORS: Record<string, string> = {
  erp: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300",
  notification: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300",
  productivity: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950 dark:text-violet-300",
  security: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300",
};

const CATEGORY_LABELS: Record<string, string> = {
  erp: "ERP",
  notification: "通知",
  productivity: "生产力",
  security: "安全",
};

const FALLBACK_PLUGINS: Plugin[] = [
  {
    id: "plugin_kingdee",
    name: "金蝶 ERP 集成",
    description: "连接金蝶 ERP HTTP 网关，同步库存、财务和薪资数据。",
    category: "erp",
    version: "1.0.0",
    icon: "database",
    is_builtin: true,
    author: "Nexus 官方",
    metadata_source: "builtin",
    connection_status: "not_installed",
    config_schema: {
      api_url: { type: "text", label: "API 地址", required: true, placeholder: "https://kingdee.example.com/api" },
      api_key: { type: "password", label: "API 密钥", required: true },
    },
  },
  {
    id: "plugin_wecom_bot",
    name: "企业微信机器人",
    description: "通过企业微信群机器人发送通知和日报。",
    category: "notification",
    version: "1.0.0",
    icon: "message-circle",
    is_builtin: true,
    author: "Nexus 官方",
    metadata_source: "builtin",
    connection_status: "not_installed",
    config_schema: {
      webhook_url: { type: "text", label: "Webhook 地址", required: true, placeholder: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" },
    },
  },
  {
    id: "plugin_email_digest",
    name: "邮件日报摘要",
    description: "按计划向指定收件人发送工作摘要邮件。",
    category: "productivity",
    version: "1.0.0",
    icon: "mail",
    is_builtin: true,
    author: "Nexus 官方",
    metadata_source: "builtin",
    connection_status: "not_installed",
    config_schema: {
      recipients: { type: "text", label: "收件人", required: true, placeholder: "多个邮箱用逗号分隔" },
      send_time: { type: "text", label: "发送时间", required: false, placeholder: "18:00" },
    },
  },
  {
    id: "plugin_data_backup",
    name: "数据自动备份",
    description: "定期导出组织数据到配置的备份存储。",
    category: "security",
    version: "1.0.0",
    icon: "shield",
    is_builtin: true,
    author: "Nexus 官方",
    metadata_source: "builtin",
    connection_status: "not_installed",
    config_schema: {},
  },
];

type PluginConfigSchema = Record<
  string,
  {
    type: string;
    label: string;
    required: boolean;
    placeholder?: string;
  }
>;

interface Plugin {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  icon: string;
  is_builtin: boolean;
  author: string;
  downloads?: number;
  rating?: number | null;
  metadata_source?: string;
  connection_status?: "not_installed" | "needs_configuration" | "configured" | "ready";
  config_schema: PluginConfigSchema;
  installed?: boolean;
  config?: Record<string, string>;
  is_active?: boolean;
  updated_at?: string;
}

interface PluginListResponse {
  success: boolean;
  data: { plugins: Plugin[] };
}

export function PluginMarketplace() {
  const [plugins, setPlugins] = useState<Plugin[]>(FALLBACK_PLUGINS);
  const [activeTab, setActiveTab] = useState("all");
  const [search, setSearch] = useState("");
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState<string | null>(null);

  const loadPlugins = async () => {
    setLoading(true);
    try {
      const res = await aiClient.fetch<PluginListResponse>("api/plugins");
      setPlugins(res.data?.plugins?.length ? res.data.plugins : FALLBACK_PLUGINS);
    } catch {
      setPlugins(FALLBACK_PLUGINS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadPlugins();
  }, []);

  const installedCount = useMemo(() => plugins.filter((plugin) => plugin.installed).length, [plugins]);

  const filteredPlugins = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return plugins.filter((plugin) => {
      const matchCategory = activeTab === "all" || activeTab === "installed" || plugin.category === activeTab;
      const matchInstalled = activeTab !== "installed" || plugin.installed;
      const matchSearch =
        !keyword ||
        plugin.name.toLowerCase().includes(keyword) ||
        plugin.description.toLowerCase().includes(keyword) ||
        plugin.category.toLowerCase().includes(keyword);
      return matchCategory && matchInstalled && matchSearch;
    });
  }, [activeTab, plugins, search]);

  const handleInstall = (plugin: Plugin) => {
    if (Object.keys(plugin.config_schema || {}).length > 0) {
      setSelectedPlugin(plugin);
      setConfigValues(plugin.config || {});
      setConfigDialogOpen(true);
      return;
    }
    void doInstall(plugin, {});
  };

  const doInstall = async (plugin: Plugin, config: Record<string, string>) => {
    setInstalling(plugin.id);
    try {
      await aiClient.fetch(`api/plugins/${plugin.id}/install`, {
        method: "POST",
        body: JSON.stringify({ config }),
      });
      await loadPlugins();
      toast.success(`${plugin.name} 已安装`);
    } catch (err) {
      toast.error(`安装失败：${(err as Error)?.message || "未知错误"}`);
    } finally {
      setInstalling(null);
      setConfigDialogOpen(false);
    }
  };

  const handleUninstall = async (plugin: Plugin) => {
    setInstalling(plugin.id);
    try {
      await aiClient.fetch(`api/plugins/${plugin.id}/uninstall`, { method: "POST" });
      await loadPlugins();
      toast.success(`${plugin.name} 已卸载`);
    } catch (err) {
      toast.error(`卸载失败：${(err as Error)?.message || "未知错误"}`);
    } finally {
      setInstalling(null);
    }
  };

  const handleConfigSave = async () => {
    if (!selectedPlugin) return;
    for (const [key, field] of Object.entries(selectedPlugin.config_schema || {})) {
      if (field.required && !configValues[key]?.trim()) {
        toast.error(`请填写${field.label}`);
        return;
      }
    }

    if (!selectedPlugin.installed) {
      await doInstall(selectedPlugin, { ...configValues });
      return;
    }

    setInstalling(selectedPlugin.id);
    try {
      await aiClient.fetch(`api/plugins/${selectedPlugin.id}/config`, {
        method: "PUT",
        body: JSON.stringify({ config: { ...configValues } }),
      });
      await loadPlugins();
      setConfigDialogOpen(false);
      toast.success("配置已更新");
    } catch (err) {
      toast.error(`配置更新失败：${(err as Error)?.message || "未知错误"}`);
    } finally {
      setInstalling(null);
    }
  };

  const openConfig = (plugin: Plugin) => {
    setSelectedPlugin(plugin);
    setConfigValues(plugin.config || {});
    setConfigDialogOpen(true);
  };

  const statusLabel = (plugin: Plugin) => {
    if (!plugin.installed) return "未安装";
    if (plugin.connection_status === "configured") return "已配置";
    if (plugin.connection_status === "ready") return "可用";
    return "待配置";
  };

  const PluginCard = ({ plugin }: { plugin: Plugin }) => {
    const IconComp = ICON_MAP[plugin.icon] || Package;
    const isLoading = installing === plugin.id;

    return (
      <Card className="relative transition-shadow hover:shadow-md">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className={cn("rounded-lg border p-2.5", CATEGORY_COLORS[plugin.category] || "bg-muted")}>
                <IconComp className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle className="truncate text-sm font-semibold">{plugin.name}</CardTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">{plugin.author}</p>
              </div>
            </div>
            <Badge variant={plugin.installed ? "default" : "outline"} className="shrink-0 text-[10px]">
              {statusLabel(plugin)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <CardDescription className="line-clamp-2 min-h-9 text-xs leading-relaxed">
            {plugin.description}
          </CardDescription>

          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className={cn("text-[10px]", CATEGORY_COLORS[plugin.category])}>
                {CATEGORY_LABELS[plugin.category] || plugin.category}
              </Badge>
              <span>v{plugin.version}</span>
            </div>
            <span className="text-xs text-muted-foreground">
              {plugin.metadata_source === "builtin" ? "官方内置" : "市场插件"}
            </span>
          </div>

          <div className="flex items-center gap-2 pt-1">
            {plugin.installed ? (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 flex-1 text-xs"
                  onClick={() => openConfig(plugin)}
                  disabled={Object.keys(plugin.config_schema || {}).length === 0}
                >
                  <Settings className="mr-1 h-3 w-3" />
                  配置
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 text-xs text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950"
                  onClick={() => handleUninstall(plugin)}
                  disabled={isLoading}
                >
                  {isLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                </Button>
              </>
            ) : (
              <Button size="sm" className="h-8 flex-1 text-xs" onClick={() => handleInstall(plugin)} disabled={isLoading}>
                {isLoading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Download className="mr-1 h-3 w-3" />}
                安装
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="mx-auto max-w-[1400px] space-y-6 p-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Puzzle className="h-6 w-6 text-primary" />
          插件市场
        </h1>
        <p className="mt-1 text-muted-foreground">安装并配置企业集成，扩展首发模块能力。</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Package className="h-5 w-5 text-primary" />
            <div>
              <p className="text-2xl font-bold">{plugins.length}</p>
              <p className="text-xs text-muted-foreground">可用插件</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Check className="h-5 w-5 text-emerald-600" />
            <div>
              <p className="text-2xl font-bold">{installedCount}</p>
              <p className="text-xs text-muted-foreground">已安装</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <ShieldCheck className="h-5 w-5 text-amber-600" />
            <div>
              <p className="text-2xl font-bold">0</p>
              <p className="text-xs text-muted-foreground">伪造下载/评分指标</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="搜索插件..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="pl-9"
        />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex h-auto flex-wrap justify-start">
          {CATEGORIES.map((category) => (
            <TabsTrigger key={category.value} value={category.value} className="gap-1.5">
              <category.icon className="h-3.5 w-3.5" />
              {category.label}
              {category.value === "installed" ? `(${installedCount})` : ""}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          正在加载插件...
        </div>
      ) : filteredPlugins.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">
          <Package className="mx-auto mb-3 h-12 w-12 opacity-30" />
          <p>{activeTab === "installed" ? "暂无已安装插件" : "没有找到匹配的插件"}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredPlugins.map((plugin) => (
            <PluginCard key={plugin.id} plugin={plugin} />
          ))}
        </div>
      )}

      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              {selectedPlugin?.installed ? "编辑配置" : "安装配置"}
            </DialogTitle>
            <DialogDescription>{selectedPlugin?.description}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {selectedPlugin &&
              Object.entries(selectedPlugin.config_schema || {}).map(([key, field]) => (
                <div key={key} className="space-y-1.5">
                  <Label htmlFor={key}>
                    {field.label}
                    {field.required && <span className="ml-1 text-red-500">*</span>}
                  </Label>
                  <Input
                    id={key}
                    type={field.type === "password" ? "password" : "text"}
                    placeholder={field.placeholder}
                    value={configValues[key] || ""}
                    onChange={(event) => setConfigValues((prev) => ({ ...prev, [key]: event.target.value }))}
                  />
                </div>
              ))}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleConfigSave} disabled={!!installing}>
              {installing ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
              {selectedPlugin?.installed ? "保存配置" : "安装"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default PluginMarketplace;
