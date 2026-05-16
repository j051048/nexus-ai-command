import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Building2,
  CheckCircle2,
  Clock,
  CreditCard,
  Eye,
  Loader2,
  LogOut,
  Pause,
  Play,
  RefreshCw,
  Settings2,
  Shield,
  Trash2,
  UserCheck,
  Users,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/components/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

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
  tier?: string;
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

function errMsg(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return String(error);
}

function confirmRisk(message: string): boolean {
  return window.confirm(
    `${message}\n\n该操作会写入审计日志。请确认你已经核对客户、套餐、配额和影响范围。`,
  );
}

export default function AdminPanel() {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [pendingBosses, setPendingBosses] = useState<PendingBoss[]>([]);
  const [organizations, setOrganizations] = useState<OrgItem[]>([]);
  const [loadingPending, setLoadingPending] = useState(true);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<OrgItem | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selectedOrg, setSelectedOrg] = useState<OrgDetail | null>(null);
  const [showOrgDetail, setShowOrgDetail] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [newPlan, setNewPlan] = useState("");
  const [planChangeReason, setPlanChangeReason] = useState("");
  const [quotaTokenLimit, setQuotaTokenLimit] = useState("");
  const [quotaApiLimit, setQuotaApiLimit] = useState("");
  const [quotaStorageLimit, setQuotaStorageLimit] = useState("");
  const [quotaReason, setQuotaReason] = useState("");
  const [trialAction, setTrialAction] = useState("start");
  const [trialPlan, setTrialPlan] = useState("professional");
  const [trialDays, setTrialDays] = useState("14");
  const [trialReason, setTrialReason] = useState("");
  const [suspendReason, setSuspendReason] = useState("");

  const totalMembers = useMemo(
    () => organizations.reduce((sum, org) => sum + (org.member_count || 0), 0),
    [organizations],
  );

  const loadPendingBosses = useCallback(async () => {
    try {
      setLoadingPending(true);
      const { data: result } = await httpClient.get("/api/organization/admin/pending-bosses");
      setPendingBosses((result.data as PendingBoss[]) || []);
    } catch (error) {
      toast.error(`加载待审批列表失败: ${errMsg(error)}`);
    } finally {
      setLoadingPending(false);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      setLoadingOrgs(true);
      const { data: result } = await httpClient.get("/api/organization/admin/organizations");
      setOrganizations((result.data as OrgItem[]) || []);
    } catch (error) {
      toast.error(`加载企业列表失败: ${errMsg(error)}`);
    } finally {
      setLoadingOrgs(false);
    }
  }, []);

  useEffect(() => {
    loadPendingBosses();
    loadOrganizations();
  }, [loadPendingBosses, loadOrganizations]);

  const resetOrgForm = () => {
    setNewPlan("");
    setPlanChangeReason("");
    setQuotaTokenLimit("");
    setQuotaApiLimit("");
    setQuotaStorageLimit("");
    setQuotaReason("");
    setTrialDays("14");
    setTrialReason("");
    setSuspendReason("");
  };

  const handleViewOrg = async (orgId: string) => {
    try {
      setDetailLoading(true);
      setShowOrgDetail(true);
      const { data: result } = await httpClient.get(`/api/admin/organizations/${orgId}`);
      setSelectedOrg(result.data as OrgDetail);
      resetOrgForm();
    } catch (error) {
      toast.error(`加载企业详情失败: ${errMsg(error)}`);
      setShowOrgDetail(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleApprove = async (userId: string, name: string) => {
    if (!confirmRisk(`确认批准 ${name} 的 Boss/管理员申请？`)) return;
    try {
      setActionLoading(userId);
      await httpClient.post(`/api/organization/admin/approve-boss/${userId}`);
      toast.success(`已批准 ${name} 的管理员权限`);
      loadPendingBosses();
    } catch (error) {
      toast.error(`审批失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (userId: string, name: string) => {
    if (!confirmRisk(`确认拒绝 ${name} 的 Boss/管理员申请？`)) return;
    try {
      setActionLoading(userId);
      await httpClient.post(`/api/organization/admin/reject-boss/${userId}`);
      toast.success(`已拒绝 ${name} 的管理员申请`);
      loadPendingBosses();
    } catch (error) {
      toast.error(`操作失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteOrg = async () => {
    if (!deleteTarget) return;
    const typed = window.prompt(`删除企业不可恢复。请输入企业名称“${deleteTarget.name}”以确认删除：`);
    if (typed !== deleteTarget.name) {
      toast.error("企业名称不匹配，已取消删除");
      return;
    }
    try {
      setActionLoading(deleteTarget.org_id);
      await httpClient.delete(`/api/organization/admin/organization/${deleteTarget.org_id}`);
      toast.success(`已删除企业 ${deleteTarget.name}`);
      setDeleteTarget(null);
      loadOrganizations();
    } catch (error) {
      toast.error(`删除失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleChangePlan = async () => {
    if (!selectedOrg || !newPlan) return;
    if (!planChangeReason.trim()) {
      toast.error("请填写变更套餐原因");
      return;
    }
    if (!confirmRisk(`确认将企业“${selectedOrg.name}”的套餐变更为 ${newPlan}？`)) return;
    try {
      setActionLoading("plan");
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/change-plan`, {
        plan: newPlan,
        reason: planChangeReason,
      });
      toast.success(`套餐已变更为 ${newPlan}`);
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (error) {
      toast.error(`变更失败: ${errMsg(error)}`);
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
      toast.error("请至少填写一个配额");
      return;
    }
    if (!quotaReason.trim()) {
      toast.error("请填写调整配额原因");
      return;
    }
    if (!confirmRisk(`确认调整企业“${selectedOrg.name}”的配额？`)) return;
    try {
      setActionLoading("quota");
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/update-quotas`, body);
      toast.success("配额已更新");
      handleViewOrg(selectedOrg.id);
    } catch (error) {
      toast.error(`更新失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleManageTrial = async () => {
    if (!selectedOrg) return;
    if (!trialReason.trim()) {
      toast.error("请填写试用期调整原因");
      return;
    }
    if (!confirmRisk(`确认调整企业“${selectedOrg.name}”的试用期？`)) return;
    try {
      setActionLoading("trial");
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/manage-trial`, {
        action: trialAction,
        plan: trialPlan,
        days: Number(trialDays) || 14,
        reason: trialReason,
      });
      toast.success("试用期已更新");
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (error) {
      toast.error(`操作失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSuspend = async () => {
    if (!selectedOrg || !suspendReason.trim()) return;
    if (!confirmRisk(`确认暂停企业“${selectedOrg.name}”？客户将无法正常使用相关服务。`)) return;
    try {
      setActionLoading("suspend");
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/suspend`, { reason: suspendReason });
      toast.success("企业已暂停");
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (error) {
      toast.error(`暂停失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleUnsuspend = async () => {
    if (!selectedOrg) return;
    if (!confirmRisk(`确认恢复企业“${selectedOrg.name}”？`)) return;
    try {
      setActionLoading("unsuspend");
      await httpClient.post(`/api/admin/organizations/${selectedOrg.id}/unsuspend`);
      toast.success("企业已恢复");
      handleViewOrg(selectedOrg.id);
      loadOrganizations();
    } catch (error) {
      toast.error(`恢复失败: ${errMsg(error)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleLogout = async () => {
    await signOut();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b bg-card/70 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-red-500 to-orange-500">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-foreground">Super Admin</h1>
              <p className="text-xs text-muted-foreground">Nexus 平台级控制台</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
              <ArrowLeft className="mr-1 h-4 w-4" />
              返回主系统
            </Button>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="mr-1 h-4 w-4" />
              退出
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard icon={UserCheck} label="待审批" value={pendingBosses.length} tone="orange" />
          <StatCard icon={Building2} label="企业总数" value={organizations.length} />
          <StatCard icon={Users} label="总用户数" value={totalMembers} />
        </div>

        <Card className="border-orange-200 bg-orange-50/60 dark:border-orange-900/40 dark:bg-orange-950/20">
          <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-orange-600" />
              <div>
                <p className="font-medium">平台级高权限区域</p>
                <p className="text-sm text-muted-foreground">
                  跨租户操作仅限 super_admin。套餐、配额、试用期、暂停和删除都会要求原因/确认并写入审计。
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">super_admin only</Badge>
              <Badge variant="outline">audited writes</Badge>
              <Badge variant="outline">typed delete confirm</Badge>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="pending" className="space-y-4">
          <TabsList>
            <TabsTrigger value="pending" className="gap-1.5">
              <UserCheck className="h-4 w-4" />
              Boss 审批
              {pendingBosses.length > 0 && <Badge variant="destructive">{pendingBosses.length}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="orgs" className="gap-1.5">
              <Building2 className="h-4 w-4" />
              企业管理
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pending">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base">待审批的管理员账号</CardTitle>
                <Button variant="outline" size="sm" onClick={loadPendingBosses}>
                  <RefreshCw className="mr-1 h-4 w-4" />
                  刷新
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {loadingPending ? (
                  <LoadingRows />
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
                          <TableCell colSpan={5} className="py-12 text-center text-muted-foreground">
                            <CheckCircle2 className="mx-auto mb-2 h-8 w-8 opacity-50" />
                            暂无待审批的管理员申请
                          </TableCell>
                        </TableRow>
                      ) : (
                        pendingBosses.map((item) => (
                          <TableRow key={item.user_id}>
                            <TableCell className="font-medium">{item.name}</TableCell>
                            <TableCell>{item.email}</TableCell>
                            <TableCell>
                              <Badge variant="outline">{item.organization_name || "-"}</Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(item.created_at).toLocaleString("zh-CN")}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1">
                                <Button
                                  size="sm"
                                  onClick={() => handleApprove(item.user_id, item.name)}
                                  disabled={actionLoading === item.user_id}
                                  className="bg-green-600 hover:bg-green-700"
                                >
                                  <CheckCircle2 className="mr-1 h-3 w-3" />
                                  批准
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleReject(item.user_id, item.name)}
                                  disabled={actionLoading === item.user_id}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <XCircle className="mr-1 h-3 w-3" />
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

          <TabsContent value="orgs">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-base">企业列表</CardTitle>
                <Button variant="outline" size="sm" onClick={loadOrganizations}>
                  <RefreshCw className="mr-1 h-4 w-4" />
                  刷新
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                {loadingOrgs ? (
                  <LoadingRows />
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
                            {org.slug === "default-org" && (
                              <Badge variant="secondary" className="ml-2 text-xs">
                                默认
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{org.slug}</code>
                          </TableCell>
                          <TableCell>{org.member_count}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(org.created_at).toLocaleDateString("zh-CN")}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              <Button variant="ghost" size="sm" onClick={() => handleViewOrg(org.org_id)}>
                                <Eye className="mr-1 h-4 w-4" />
                                管理
                              </Button>
                              {org.slug !== "default-org" && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-destructive hover:text-destructive"
                                  onClick={() => setDeleteTarget(org)}
                                >
                                  <Trash2 className="h-4 w-4" />
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

      <Dialog open={showOrgDetail} onOpenChange={setShowOrgDetail}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>企业管理</DialogTitle>
            <DialogDescription>查看和管理企业信息、订阅、配额和状态</DialogDescription>
          </DialogHeader>

          {detailLoading ? (
            <LoadingRows />
          ) : selectedOrg ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <Detail label="名称" value={selectedOrg.name} />
                <Detail label="状态" value={selectedOrg.status} />
                <Detail label="用户数" value={selectedOrg.user_count ?? "-"} />
                <Detail label="AI 调用(30天)" value={selectedOrg.ai_calls_30d ?? "-"} />
                <Detail label="当前套餐" value={selectedOrg.subscription?.plan || selectedOrg.plan || "free"} />
                <Detail label="创建时间" value={new Date(selectedOrg.created_at).toLocaleString("zh-CN")} />
              </div>

              {selectedOrg.status === "active" ? (
                <DangerSection title="暂停企业" icon={Pause}>
                  <div className="flex gap-2">
                    <Input
                      className="h-8 flex-1"
                      placeholder="暂停原因..."
                      value={suspendReason}
                      onChange={(event) => setSuspendReason(event.target.value)}
                    />
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-8"
                      disabled={!suspendReason.trim() || actionLoading === "suspend"}
                      onClick={handleSuspend}
                    >
                      确认暂停
                    </Button>
                  </div>
                </DangerSection>
              ) : (
                <DangerSection title="恢复企业" icon={Play}>
                  <Button size="sm" disabled={actionLoading === "unsuspend"} onClick={handleUnsuspend}>
                    <Play className="mr-1 h-4 w-4" />
                    恢复组织
                  </Button>
                </DangerSection>
              )}

              <DangerSection title="变更订阅套餐" icon={CreditCard}>
                <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
                  <div>
                    <Label className="text-xs">目标套餐</Label>
                    <Select value={newPlan} onValueChange={setNewPlan}>
                      <SelectTrigger className="h-8">
                        <SelectValue placeholder="选择套餐" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="free">Free</SelectItem>
                        <SelectItem value="starter">Starter</SelectItem>
                        <SelectItem value="professional">Professional</SelectItem>
                        <SelectItem value="enterprise">Enterprise</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">变更原因</Label>
                    <Input
                      className="h-8"
                      value={planChangeReason}
                      onChange={(event) => setPlanChangeReason(event.target.value)}
                    />
                  </div>
                  <Button size="sm" className="h-8" disabled={!newPlan || actionLoading === "plan"} onClick={handleChangePlan}>
                    确认变更
                  </Button>
                </div>
              </DangerSection>

              <DangerSection title="调整配额" icon={Settings2}>
                <div className="grid gap-2 sm:grid-cols-3">
                  <Input className="h-8" type="number" placeholder="月 Token 限额" value={quotaTokenLimit} onChange={(event) => setQuotaTokenLimit(event.target.value)} />
                  <Input className="h-8" type="number" placeholder="月 API 限额" value={quotaApiLimit} onChange={(event) => setQuotaApiLimit(event.target.value)} />
                  <Input className="h-8" type="number" placeholder="存储限额 MB" value={quotaStorageLimit} onChange={(event) => setQuotaStorageLimit(event.target.value)} />
                </div>
                <div className="mt-2 flex gap-2">
                  <Input className="h-8 flex-1" placeholder="调整原因" value={quotaReason} onChange={(event) => setQuotaReason(event.target.value)} />
                  <Button size="sm" className="h-8" disabled={actionLoading === "quota"} onClick={handleUpdateQuotas}>
                    确认调整
                  </Button>
                </div>
              </DangerSection>

              <DangerSection title="管理试用期" icon={Clock}>
                <div className="grid gap-2 sm:grid-cols-[120px_150px_100px_1fr_auto] sm:items-end">
                  <Select value={trialAction} onValueChange={setTrialAction}>
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="start">开启</SelectItem>
                      <SelectItem value="extend">延长</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={trialPlan} onValueChange={setTrialPlan}>
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starter">Starter</SelectItem>
                      <SelectItem value="professional">Professional</SelectItem>
                      <SelectItem value="enterprise">Enterprise</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input className="h-8" type="number" value={trialDays} onChange={(event) => setTrialDays(event.target.value)} />
                  <Input className="h-8" placeholder="原因" value={trialReason} onChange={(event) => setTrialReason(event.target.value)} />
                  <Button size="sm" className="h-8" disabled={actionLoading === "trial"} onClick={handleManageTrial}>
                    确认
                  </Button>
                </div>
              </DangerSection>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowOrgDetail(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              确认删除企业？
            </AlertDialogTitle>
            <AlertDialogDescription>
              将删除企业 <strong>{deleteTarget?.name}</strong> 及其关联数据。点击确认后仍需输入企业名称二次确认。
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

function StatCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  tone?: "orange";
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className={tone === "orange" ? "text-3xl font-bold text-orange-500" : "text-3xl font-bold"}>
              {value.toLocaleString()}
            </p>
          </div>
          <Icon className="h-10 w-10 text-muted-foreground/20" />
        </div>
      </CardContent>
    </Card>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}

function DangerSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2 border-t pt-3">
      <p className="flex items-center gap-1 text-sm font-medium">
        <Icon className="h-4 w-4" />
        {title}
      </p>
      {children}
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    </div>
  );
}
