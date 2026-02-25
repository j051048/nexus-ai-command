import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { supabase } from '@/integrations/supabase/client';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  Building2,
  Users,
  Activity,
  Brain,
  Search,
  Pause,
  Play,
  ShieldCheck,
  Server,
  Database,
  Cpu,
  ScrollText,
  RefreshCw,
} from 'lucide-react';

// ============== Types ==============

interface Organization {
  id: string;
  name: string;
  status: string;
  plan: string;
  subscription_status: string;
  created_at: string;
  user_count?: number;
  ai_calls_30d?: number;
}

interface PlatformStats {
  total_organizations: number;
  active_organizations: number;
  total_users: number;
  monthly_active_users: number;
  total_ai_calls_30d: number;
  updated_at: string;
}

interface SystemHealth {
  overall: string;
  services: Record<string, { status: string; error?: string; provider?: string }>;
  checked_at: string;
}

interface AuditLog {
  id: string;
  action: string;
  user_id: string;
  organization_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

// ============== API Helpers ==============

const API_BASE = `${import.meta.env.VITE_API_BASE_URL}/api/admin`;

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token || '';
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    ...options,
  });
  if (!res.ok) throw new Error(`API 请求失败: ${res.status}`);
  const json = await res.json();
  return json.data ?? json;
}

// ============== Component ==============

function SuperAdminDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [showOrgDetail, setShowOrgDetail] = useState(false);
  const [suspendReason, setSuspendReason] = useState('');

  // ---------- 数据加载 ----------

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchAPI<PlatformStats>('/stats');
      setStats(data);
    } catch (e) {
      console.error('加载平台统计失败', e);
    }
  }, []);

  const loadHealth = useCallback(async () => {
    try {
      const data = await fetchAPI<SystemHealth>('/system-health');
      setHealth(data);
    } catch (e) {
      console.error('加载系统健康失败', e);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page: '1', limit: '50' });
      if (searchTerm) params.set('search', searchTerm);
      if (statusFilter !== 'all') params.set('status', statusFilter);
      const data = await fetchAPI<Organization[]>(`/organizations?${params}`);
      setOrganizations(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('加载组织列表失败', e);
    }
  }, [searchTerm, statusFilter]);

  const loadAuditLogs = useCallback(async () => {
    try {
      const data = await fetchAPI<AuditLog[]>('/audit-logs?limit=100');
      setAuditLogs(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('加载审计日志失败', e);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([loadStats(), loadHealth(), loadOrganizations()]);
      setLoading(false);
    };
    init();
  }, [loadStats, loadHealth, loadOrganizations]);

  useEffect(() => {
    if (activeTab === 'audit') loadAuditLogs();
  }, [activeTab, loadAuditLogs]);

  // ---------- 操作 ----------

  const handleViewOrg = async (org: Organization) => {
    try {
      const detail = await fetchAPI<Organization>(`/organizations/${org.id}`);
      setSelectedOrg(detail);
      setShowOrgDetail(true);
    } catch {
      toast.error('加载组织详情失败');
    }
  };

  const handleSuspend = async (orgId: string) => {
    if (!suspendReason.trim()) {
      toast.error('请填写暂停原因');
      return;
    }
    try {
      await fetchAPI(`/organizations/${orgId}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ reason: suspendReason }),
      });
      toast.success('组织已暂停');
      setSuspendReason('');
      setShowOrgDetail(false);
      loadOrganizations();
    } catch {
      toast.error('暂停操作失败');
    }
  };

  const handleUnsuspend = async (orgId: string) => {
    try {
      await fetchAPI(`/organizations/${orgId}/unsuspend`, { method: 'POST' });
      toast.success('组织已恢复');
      setShowOrgDetail(false);
      loadOrganizations();
    } catch {
      toast.error('恢复操作失败');
    }
  };

  // ---------- Helpers ----------

  const healthColor = (status: string) => {
    if (status === 'healthy') return 'bg-green-500';
    if (status === 'degraded' || status === 'unconfigured') return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const statusBadge = (status: string) => {
    if (status === 'active') return <Badge className="bg-green-100 text-green-800">活跃</Badge>;
    if (status === 'suspended') return <Badge variant="destructive">已暂停</Badge>;
    return <Badge variant="secondary">{status}</Badge>;
  };

  // ---------- Render ----------

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* 标题 */}
      <div className="flex items-center gap-3">
        <ShieldCheck className="w-7 h-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold tracking-tight">超级管理员控制台</h1>
          <p className="text-sm text-muted-foreground">跨组织管理、平台监控和系统运维</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="organizations">组织管理</TabsTrigger>
          <TabsTrigger value="health">系统健康</TabsTrigger>
          <TabsTrigger value="audit">审计日志</TabsTrigger>
        </TabsList>

        {/* ========== 概览 ========== */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={Building2} label="总组织数" value={stats?.total_organizations ?? 0} sub={`活跃: ${stats?.active_organizations ?? 0}`} />
            <StatCard icon={Users} label="总用户数" value={stats?.total_users ?? 0} sub={`MAU: ${stats?.monthly_active_users ?? 0}`} />
            <StatCard icon={Activity} label="MAU" value={stats?.monthly_active_users ?? 0} sub="近30天活跃用户" />
            <StatCard icon={Brain} label="AI 调用量" value={stats?.total_ai_calls_30d ?? 0} sub="近30天" />
          </div>

          {/* 系统健康摘要 */}
          {health && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Server className="w-4 h-4" />
                  系统状态
                  <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthColor(health.overall)}`} />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Object.entries(health.services).map(([name, svc]) => (
                    <div key={name} className="flex items-center gap-2 p-2 rounded-lg border">
                      <span className={`w-2 h-2 rounded-full ${healthColor(svc.status)}`} />
                      <span className="text-sm capitalize">{name}</span>
                      <span className="text-xs text-muted-foreground ml-auto">{svc.status}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ========== 组织管理 ========== */}
        <TabsContent value="organizations" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索组织名称..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="状态筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="active">活跃</SelectItem>
                <SelectItem value="suspended">已暂停</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={loadOrganizations}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>组织名称</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>订阅计划</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {organizations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                        暂无数据
                      </TableCell>
                    </TableRow>
                  ) : (
                    organizations.map((org) => (
                      <TableRow key={org.id}>
                        <TableCell className="font-medium">{org.name}</TableCell>
                        <TableCell>{statusBadge(org.status)}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{org.plan || 'free'}</Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(org.created_at).toLocaleDateString('zh-CN')}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => handleViewOrg(org)}>
                            查看
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ========== 系统健康 ========== */}
        <TabsContent value="health" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">系统健康详情</h2>
            <Button variant="outline" size="sm" onClick={loadHealth}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新
            </Button>
          </div>

          {health && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(health.services).map(([name, svc]) => {
                const icons: Record<string, React.ElementType> = {
                  database: Database,
                  cache: Cpu,
                  ai: Brain,
                  queue: Server,
                };
                const Icon = icons[name] || Server;

                return (
                  <Card key={name}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Icon className="w-4 h-4" />
                        <span className="capitalize">{name}</span>
                        <span className={`ml-auto w-3 h-3 rounded-full ${healthColor(svc.status)}`} />
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-sm space-y-1">
                        <p>状态: <span className="font-medium">{svc.status}</span></p>
                        {svc.provider && <p>服务商: {svc.provider}</p>}
                        {svc.error && (
                          <p className="text-destructive text-xs">错误: {svc.error}</p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {health && (
            <p className="text-xs text-muted-foreground">
              上次检查: {new Date(health.checked_at).toLocaleString('zh-CN')}
            </p>
          )}
        </TabsContent>

        {/* ========== 审计日志 ========== */}
        <TabsContent value="audit" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <ScrollText className="w-5 h-5" />
              全局审计日志
            </h2>
            <Button variant="outline" size="sm" onClick={loadAuditLogs}>
              <RefreshCw className="w-4 h-4 mr-1" />
              刷新
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>操作</TableHead>
                    <TableHead>用户 ID</TableHead>
                    <TableHead>组织 ID</TableHead>
                    <TableHead>时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLogs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                        暂无审计记录
                      </TableCell>
                    </TableRow>
                  ) : (
                    auditLogs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell>
                          <Badge variant="outline">{log.action}</Badge>
                        </TableCell>
                        <TableCell className="text-xs font-mono">
                          {log.user_id?.substring(0, 8)}...
                        </TableCell>
                        <TableCell className="text-xs font-mono">
                          {log.organization_id?.substring(0, 8)}...
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(log.created_at).toLocaleString('zh-CN')}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ========== 组织详情弹窗 ========== */}
      <Dialog open={showOrgDetail} onOpenChange={setShowOrgDetail}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>组织详情</DialogTitle>
            <DialogDescription>查看和管理组织信息</DialogDescription>
          </DialogHeader>

          {selectedOrg && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground">名称</p>
                  <p className="font-medium">{selectedOrg.name}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">状态</p>
                  <p>{statusBadge(selectedOrg.status)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">用户数</p>
                  <p className="font-medium">{selectedOrg.user_count ?? '-'}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">AI 调用量 (30天)</p>
                  <p className="font-medium">{selectedOrg.ai_calls_30d ?? '-'}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">订阅计划</p>
                  <Badge variant="outline">{selectedOrg.plan || 'free'}</Badge>
                </div>
                <div>
                  <p className="text-muted-foreground">创建时间</p>
                  <p className="text-xs">{new Date(selectedOrg.created_at).toLocaleString('zh-CN')}</p>
                </div>
              </div>

              {selectedOrg.status === 'active' && (
                <div className="space-y-2 border-t pt-3">
                  <p className="text-sm font-medium text-destructive">暂停组织</p>
                  <Input
                    placeholder="请输入暂停原因..."
                    value={suspendReason}
                    onChange={(e) => setSuspendReason(e.target.value)}
                  />
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleSuspend(selectedOrg.id)}
                    disabled={!suspendReason.trim()}
                  >
                    <Pause className="w-4 h-4 mr-1" />
                    确认暂停
                  </Button>
                </div>
              )}

              {selectedOrg.status === 'suspended' && (
                <div className="border-t pt-3">
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => handleUnsuspend(selectedOrg.id)}
                  >
                    <Play className="w-4 h-4 mr-1" />
                    恢复组织
                  </Button>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowOrgDetail(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============== Stat Card ==============

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Icon className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold">{value.toLocaleString()}</p>
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default SuperAdminDashboard;
