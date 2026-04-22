import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
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
  Shield,
  Users,
  Building2,
  CheckCircle2,
  XCircle,
  Trash2,
  ArrowLeft,
  LogOut,
  RefreshCw,
  Loader2,
  UserCheck,
  AlertTriangle,
  CreditCard,
  Settings2,
  Clock,
  Eye,
  Pause,
  Play,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

// ============== Types ==============

interface PendingBoss {
  user_id: string;
  name: string;
  email: string;
  created_at: string;
  organization_name: string;
}

interface OrgItem {
  org_id: string;
  name: string;
  slug: string;
  member_count: number;
  created_at: string;
}

interface OrgDetail {
  id: string;
  name: string;
  status: string;
  plan: string;
  tier: string;
  created_at: string;
  user_count?: number;
  ai_calls_30d?: number;
  subscription?: {
    plan: string;
    status: string;
    current_period_end?: string;
  } | null;
  quotas?: {
    monthly_token_limit?: number;
    monthly_api_call_limit?: number;
    storage_limit_mb?: number;
  } | null;
}

// ============== Helpers ==============

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (e && typeof e === 'object' && 'message' in e) return String((e as { message: unknown }).message);
  return String(e);
}

// ============== Component ==============

function AdminPanel() {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [pendingBosses, setPendingBosses] = useState<PendingBoss[]>([]);
  const [organizations, setOrganizations] = useState<OrgItem[]>([]);
  const [loadingPending, setLoadingPending] = useState(true);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<OrgItem | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // 组织详情弹窗状态
  const [selectedOrg, setSelectedOrg] = useState<OrgDetail | null>(null);
  const [showOrgDetail, setShowOrgDetail] = useState(false);
  const [newPlan, setNewPlan] = useState('');
  const [planChangeReason, setPlanChangeReason] = useState('');
  const [quotaTokenLimit, setQuotaTokenLimit] = useState('');
  const [quotaApiLimit, setQuotaApiLimit] = useState('');
  const [quotaStorageLimit, setQuotaStorageLimit] = useState('');
  const [quotaReason, setQuotaReason] = useState('');
  const [trialAction, setTrialAction] = useState('start');
  const [trialPlan, setTrialPlan] = useState('professional');
  const [trialDays, setTrialDays] = useState('14');
  const [trialReason, setTrialReason] = useState('');
  const [suspendReason, setSuspendReason] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);

  // ---------- Load Data ----------

  const loadPendingBosses = useCallback(async () => {
    try {
      setLoadingPending(true);
      const { data: result } = await httpClient.get('/api/organization/admin/pending-bosses');
      setPendingBosses((result.data as PendingBoss[]) || []);
    } catch (e) {
      toast.error(`加载待审批列表失败: ${errMsg(e)}`);
    } finally {
      setLoadingPending(false);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      setLoadingOrgs(true);
      const { data: result } = await httpClient.get('/api/organization/admin/organizations');
      setOrganizations((result.data as OrgItem[]) || []);
    } catch (e) {
      toast.error(`加载企业列表失败: ${errMsg(e)}`);
    } finally {
      setLoadingOrgs(false);
    }
  }, []);

  useEffect(() => {
    loadPendingBosses();
    loadOrganizations();
  }, [loadPendingBosses, loadOrganizations]);

  // ---------- Actions ----------

  const handleApprove = async (userId: string, name: string) => {
    try {
      setActionLoading(userId);
      await httpClient.post(`/api/organization/admin/approve-boss/${userId}`);
      toast.success(`已批准 ${name} 的管理员权限`);
      loadPendingBosses();
    } catch (e) {
      toast.error(`审批失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (userId: string, name: string) => {
    try {
      setActionLoading(userId);
      await httpClient.post(`/api/organization/admin/reject-boss/${userId}`);
      toast.success(`已拒绝 ${name} 的管理员申请`);
      loadPendingBosses();
    } catch (e) {
      toast.error(`操作失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteOrg = async () => {
    if (!deleteTarget) return;
    try {
      setActionLoading(deleteTarget.org_id);
      await httpClient.delete(`/api/organization/admin/organization/${deleteTarget.org_id}`);
      toast.success(`已删除企业: ${deleteTarget.name}`);
      setDeleteTarget(null);
      loadOrganizations();
    } catch (e) {
      toast.error(`删除失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleViewOrg = async (orgId: string) => {
    try {
      setDetailLoading(true);
      setShowOrgDetail(true);
      const { data: result } = await httpClient.get(`/api/admin/organizations/${orgId}`);
      setSelectedOrg(result.data as OrgDetail);
      setNewPlan('');
      setPlanChangeReason('');
      setQuotaTokenLimit('');
      setQuotaApiLimit('');
      setQuotaStorageLimit('');
      setQuotaReason('');
      setSuspendReason('');
      setTrialDays('14');
      setTrialReason('');
    } catch (e) {
      toast.error(`加载详情失败: ${errMsg(e)}`);
      setShowOrgDetail(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleChangePlan = async () => {
    if (!selectedOrg || !newPlan) return;
    try {
      setActionLoading('plan');
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/change-plan`, {
        plan: newPlan, reason: planChangeReason,
      });
      toast.success(`计划已变更为 ${newPlan}`);
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (e) {
      toast.error(`变更失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUpdateQuotas = async () => {
    if (!selectedOrg) return;
    const body: Record<string, unknown> = { reason: quotaReason };
    if (quotaTokenLimit) body.monthly_token_limit = Number(quotaTokenLimit);
    if (quotaApiLimit) body.monthly_api_call_limit = Number(quotaApiLimit);
    if (quotaStorageLimit) body.storage_limit_mb = Number(quotaStorageLimit);
    if (!quotaTokenLimit && !quotaApiLimit && !quotaStorageLimit) {
      toast.error('请至少填写一个配额'); return;
    }
    try {
      setActionLoading('quota');
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/update-quotas`, body);
      toast.success('配额已更新');
      handleViewOrg(selectedOrg.id);
    } catch (e) {
      toast.error(`更新失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleManageTrial = async () => {
    if (!selectedOrg) return;
    try {
      setActionLoading('trial');
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/manage-trial`, {
        action: trialAction, plan: trialPlan, days: Number(trialDays) || 14, reason: trialReason,
      });
      toast.success(trialAction === 'start' ? '试用已开启' : '试用已延长');
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (e) {
      toast.error(`操作失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSuspend = async () => {
    if (!selectedOrg || !suspendReason.trim()) return;
    try {
      setActionLoading('suspend');
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/suspend`, { reason: suspendReason });
      toast.success('组织已暂停');
      setSuspendReason('');
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (e) {
      toast.error(`暂停失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnsuspend = async () => {
    if (!selectedOrg) return;
    try {
      setActionLoading('unsuspend');
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/unsuspend`);
      toast.success('组织已恢复');
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (e) {
      toast.error(`恢复失败: ${errMsg(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleLogout = async () => {
    await signOut();
    navigate('/login');
  };

  // ---------- Render ----------

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-foreground">Super Admin</h1>
              <p className="text-xs text-muted-foreground">Nexus 超级管理员控制台</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              返回主系统
            </Button>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="w-4 h-4 mr-1" />
              退出
            </Button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">待审批</p>
                  <p className="text-3xl font-bold text-orange-500">{pendingBosses.length}</p>
                </div>
                <UserCheck className="w-10 h-10 text-orange-500/20" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">企业总数</p>
                  <p className="text-3xl font-bold">{organizations.length}</p>
                </div>
                <Building2 className="w-10 h-10 text-muted-foreground/20" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">总用户数</p>
                  <p className="text-3xl font-bold">
                    {organizations.reduce((sum, o) => sum + o.member_count, 0)}
                  </p>
                </div>
                <Users className="w-10 h-10 text-muted-foreground/20" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="pending" className="space-y-4">
          <TabsList>
            <TabsTrigger value="pending" className="flex items-center gap-1.5">
              <UserCheck className="w-4 h-4" />
              Boss 审批
              {pendingBosses.length > 0 && (
                <Badge variant="destructive" className="ml-1 h-5 px-1.5 text-xs">
                  {pendingBosses.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="orgs" className="flex items-center gap-1.5">
              <Building2 className="w-4 h-4" />
              企业管理
            </TabsTrigger>
          </TabsList>

          {/* ======= Pending Boss Approvals ======= */}
          <TabsContent value="pending">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base">待审批的管理员账号</CardTitle>
                <Button variant="outline" size="sm" onClick={loadPendingBosses}>
                  <RefreshCw className="w-4 h-4 mr-1" />
                  刷新
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {loadingPending ? (
                  <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>姓名</TableHead>
                        <TableHead>邮箱</TableHead>
                        <TableHead>所属企业</TableHead>
                        <TableHead>注册时间</TableHead>
                        <TableHead className="text-right">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pendingBosses.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center py-16 text-muted-foreground">
                            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                            <p>暂无待审批的管理员申请</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        pendingBosses.map((item) => (
                          <TableRow key={item.user_id}>
                            <TableCell className="font-medium">{item.name}</TableCell>
                            <TableCell className="text-sm">{item.email}</TableCell>
                            <TableCell>
                              <Badge variant="outline">{item.organization_name}</Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(item.created_at).toLocaleString('zh-CN')}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  size="sm"
                                  onClick={() => handleApprove(item.user_id, item.name)}
                                  disabled={actionLoading === item.user_id}
                                  className="bg-green-600 hover:bg-green-700"
                                >
                                  {actionLoading === item.user_id ? (
                                    <Loader2 className="w-3 h-3 animate-spin mr-1" />
                                  ) : (
                                    <CheckCircle2 className="w-3 h-3 mr-1" />
                                  )}
                                  批准
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleReject(item.user_id, item.name)}
                                  disabled={actionLoading === item.user_id}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <XCircle className="w-3 h-3 mr-1" />
                                  拒绝
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======= Organization Management ======= */}
          <TabsContent value="orgs">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base">企业列表</CardTitle>
                <Button variant="outline" size="sm" onClick={loadOrganizations}>
                  <RefreshCw className="w-4 h-4 mr-1" />
                  刷新
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {loadingOrgs ? (
                  <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>企业名称</TableHead>
                        <TableHead>Slug</TableHead>
                        <TableHead>成员数</TableHead>
                        <TableHead>创建时间</TableHead>
                        <TableHead className="text-right">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {organizations.map((org) => (
                        <TableRow key={org.org_id}>
                          <TableCell className="font-medium">
                            {org.name}
                            {org.slug === 'default-org' && (
                              <Badge variant="secondary" className="ml-2 text-xs">默认</Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{org.slug}</code>
                          </TableCell>
                          <TableCell>
                            <span className="flex items-center gap-1">
                              <Users className="w-3 h-3 text-muted-foreground" />
                              {org.member_count}
                            </span>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(org.created_at).toLocaleDateString('zh-CN')}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleViewOrg(org.org_id)}
                              >
                                <Eye className="w-4 h-4 mr-1" />
                                管理
                              </Button>
                              {org.slug !== 'default-org' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-destructive hover:text-destructive"
                                  onClick={() => setDeleteTarget(org)}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>

      {/* ======= Organization Detail / Management Dialog ======= */}
      <Dialog open={showOrgDetail} onOpenChange={setShowOrgDetail}>
        <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>企业管理</DialogTitle>
            <DialogDescription>查看和管理企业信息、订阅、配额</DialogDescription>
          </DialogHeader>

          {detailLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : selectedOrg && (
            <div className="space-y-4">
              {/* 基本信息 */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-muted-foreground">名称</p>
                  <p className="font-medium">{selectedOrg.name}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">状态</p>
                  <Badge className={selectedOrg.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                    {selectedOrg.status === 'active' ? '活跃' : '已暂停'}
                  </Badge>
                </div>
                <div>
                  <p className="text-muted-foreground">用户数</p>
                  <p className="font-medium">{selectedOrg.user_count ?? '-'}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">AI 调用 (30天)</p>
                  <p className="font-medium">{selectedOrg.ai_calls_30d ?? '-'}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">当前计划</p>
                  <Badge variant="outline">{selectedOrg.subscription?.plan || selectedOrg.plan || 'free'}</Badge>
                  {selectedOrg.subscription?.status === 'trialing' && (
                    <Badge className="ml-1 bg-blue-100 text-blue-800">试用中</Badge>
                  )}
                </div>
                <div>
                  <p className="text-muted-foreground">创建时间</p>
                  <p className="text-xs">{new Date(selectedOrg.created_at).toLocaleString('zh-CN')}</p>
                </div>
              </div>

              {/* 暂停/恢复 */}
              {selectedOrg.status === 'active' && (
                <div className="space-y-2 border-t pt-3">
                  <p className="text-sm font-medium text-destructive flex items-center gap-1">
                    <Pause className="w-4 h-4" /> 暂停组织
                  </p>
                  <div className="flex gap-2">
                    <Input className="h-8 flex-1" placeholder="暂停原因..." value={suspendReason} onChange={(e) => setSuspendReason(e.target.value)} />
                    <Button variant="destructive" size="sm" className="h-8" disabled={!suspendReason.trim() || actionLoading === 'suspend'} onClick={handleSuspend}>
                      确认暂停
                    </Button>
                  </div>
                </div>
              )}
              {selectedOrg.status === 'suspended' && (
                <div className="border-t pt-3">
                  <Button size="sm" disabled={actionLoading === 'unsuspend'} onClick={handleUnsuspend}>
                    <Play className="w-4 h-4 mr-1" /> 恢复组织
                  </Button>
                </div>
              )}

              {/* 变更订阅计划 */}
              <div className="border-t pt-3 space-y-2">
                <p className="text-sm font-medium flex items-center gap-1">
                  <CreditCard className="w-4 h-4" /> 变更订阅计划
                </p>
                {selectedOrg.subscription && (
                  <p className="text-xs text-muted-foreground">
                    当前: {selectedOrg.subscription.plan} ({selectedOrg.subscription.status})
                    {selectedOrg.subscription.current_period_end && (
                      <> · 到期: {new Date(selectedOrg.subscription.current_period_end).toLocaleDateString('zh-CN')}</>
                    )}
                  </p>
                )}
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <Label className="text-xs">目标计划</Label>
                    <Select value={newPlan} onValueChange={setNewPlan}>
                      <SelectTrigger className="h-8"><SelectValue placeholder="选择计划" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="free">Free</SelectItem>
                        <SelectItem value="starter">Starter ($29/月)</SelectItem>
                        <SelectItem value="professional">Professional ($99/月)</SelectItem>
                        <SelectItem value="enterprise">Enterprise ($299/月)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex-1">
                    <Label className="text-xs">原因 (可选)</Label>
                    <Input className="h-8" placeholder="变更原因" value={planChangeReason} onChange={(e) => setPlanChangeReason(e.target.value)} />
                  </div>
                  <Button size="sm" className="h-8" disabled={!newPlan || actionLoading === 'plan'} onClick={handleChangePlan}>
                    确认变更
                  </Button>
                </div>
              </div>

              {/* 调整配额 */}
              <div className="border-t pt-3 space-y-2">
                <p className="text-sm font-medium flex items-center gap-1">
                  <Settings2 className="w-4 h-4" /> 调整配额
                </p>
                {selectedOrg.quotas && (
                  <p className="text-xs text-muted-foreground">
                    当前: Token {selectedOrg.quotas.monthly_token_limit?.toLocaleString() ?? '-'}
                    · API {selectedOrg.quotas.monthly_api_call_limit?.toLocaleString() ?? '-'}
                    · 存储 {selectedOrg.quotas.storage_limit_mb ?? '-'} MB
                  </p>
                )}
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <Label className="text-xs">月Token限额</Label>
                    <Input className="h-8" type="number" placeholder="如 500000" value={quotaTokenLimit} onChange={(e) => setQuotaTokenLimit(e.target.value)} />
                  </div>
                  <div>
                    <Label className="text-xs">月API调用限额</Label>
                    <Input className="h-8" type="number" placeholder="如 5000" value={quotaApiLimit} onChange={(e) => setQuotaApiLimit(e.target.value)} />
                  </div>
                  <div>
                    <Label className="text-xs">存储限额(MB)</Label>
                    <Input className="h-8" type="number" placeholder="如 1000" value={quotaStorageLimit} onChange={(e) => setQuotaStorageLimit(e.target.value)} />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Input className="h-8 flex-1" placeholder="调整原因 (可选)" value={quotaReason} onChange={(e) => setQuotaReason(e.target.value)} />
                  <Button size="sm" className="h-8" disabled={actionLoading === 'quota'} onClick={handleUpdateQuotas}>
                    确认调整
                  </Button>
                </div>
              </div>

              {/* 管理试用期 */}
              <div className="border-t pt-3 space-y-2">
                <p className="text-sm font-medium flex items-center gap-1">
                  <Clock className="w-4 h-4" /> 管理试用期
                </p>
                <div className="flex gap-2 items-end">
                  <div>
                    <Label className="text-xs">操作</Label>
                    <Select value={trialAction} onValueChange={setTrialAction}>
                      <SelectTrigger className="h-8 w-24"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="start">开启</SelectItem>
                        <SelectItem value="extend">延长</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">计划</Label>
                    <Select value={trialPlan} onValueChange={setTrialPlan}>
                      <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="starter">Starter</SelectItem>
                        <SelectItem value="professional">Professional</SelectItem>
                        <SelectItem value="enterprise">Enterprise</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">天数</Label>
                    <Input className="h-8 w-20" type="number" value={trialDays} onChange={(e) => setTrialDays(e.target.value)} />
                  </div>
                  <Button size="sm" className="h-8" disabled={actionLoading === 'trial'} onClick={handleManageTrial}>
                    确认
                  </Button>
                </div>
                <Input className="h-8" placeholder="原因 (可选)" value={trialReason} onChange={(e) => setTrialReason(e.target.value)} />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowOrgDetail(false)}>关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ======= Delete Confirmation ======= */}
      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-destructive" />
              确认删除企业？
            </AlertDialogTitle>
            <AlertDialogDescription>
              将删除企业 <strong>{deleteTarget?.name}</strong> 及其关联数据。
              该企业下的 <strong>{deleteTarget?.member_count}</strong> 名用户将被移至默认企业。
              <br /><br />
              此操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteOrg}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default AdminPanel;
