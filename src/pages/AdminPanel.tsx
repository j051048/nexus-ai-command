import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
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
} from 'lucide-react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

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

  // ---------- Load Data ----------

  const loadPendingBosses = useCallback(async () => {
    try {
      setLoadingPending(true);
      const { data, error } = await supabase.rpc('admin_list_pending_bosses');
      if (error) throw error;
      setPendingBosses((data as PendingBoss[]) || []);
    } catch (e) {
      toast.error(`加载待审批列表失败: ${errMsg(e)}`);
    } finally {
      setLoadingPending(false);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      setLoadingOrgs(true);
      const { data, error } = await supabase.rpc('admin_list_organizations');
      if (error) throw error;
      setOrganizations((data as OrgItem[]) || []);
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
      const { error } = await supabase.rpc('admin_approve_boss', { _user_id: userId });
      if (error) throw error;
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
      const { error } = await supabase.rpc('admin_reject_boss', { _user_id: userId });
      if (error) throw error;
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
      const { error } = await supabase.rpc('admin_delete_organization', { _org_id: deleteTarget.org_id });
      if (error) throw error;
      toast.success(`已删除企业: ${deleteTarget.name}`);
      setDeleteTarget(null);
      loadOrganizations();
    } catch (e) {
      toast.error(`删除失败: ${errMsg(e)}`);
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
                            {org.slug === 'default-org' ? (
                              <Badge variant="outline" className="text-xs">受保护</Badge>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                onClick={() => setDeleteTarget(org)}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            )}
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
