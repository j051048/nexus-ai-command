import { type ElementType, type ReactNode, useDeferredValue, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Check,
  Clock3,
  Eye,
  FileClock,
  LogOut,
  RefreshCw,
  Search,
  ShieldCheck,
  UserCheck,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '@/components/auth/AuthContext';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import { AccessRequestQueue } from '@/components/super-admin/AccessRequestQueue';
import { OrganizationAccessDialog } from '@/components/super-admin/OrganizationAccessDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  type AdminOrganization,
  type AuditLog,
  type PendingBoss,
  useAdminAuditLogs,
  useAdminOrganizations,
  useBossDecision,
  usePendingBosses,
  usePlatformStats,
  useSubscriptionRequests,
} from '@/hooks/useSuperAdminConsole';

const PLAN_NAMES: Record<string, string> = {
  free: '未开通',
  starter: '团队版',
  professional: '专业版',
  enterprise: '企业版',
};

const ACCESS_STATE: Record<string, { label: string; className?: string }> = {
  active: { label: '已生效', className: 'bg-success/10 text-success hover:bg-success/10' },
  expired: { label: '已到期', className: 'bg-destructive/10 text-destructive hover:bg-destructive/10' },
  past_due: { label: '待核对', className: 'bg-amber-500/10 text-amber-700 hover:bg-amber-500/10' },
  suspended: { label: '已停用' },
  cancelled: { label: '已取消' },
  free: { label: '未开通' },
  unconfigured: { label: '未配置' },
};

const AUDIT_ACTIONS: Record<string, string> = {
  admin_set_subscription_access: '调整会员权益',
  admin_manage_trial: '调整试用期',
  admin_change_plan: '变更套餐',
  admin_update_quotas: '调整配额',
  admin_suspend_organization: '停用企业',
  admin_unsuspend_organization: '恢复企业',
};

export default function AdminPanel() {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search.trim());
  const [selectedOrganization, setSelectedOrganization] = useState<AdminOrganization | null>(null);
  const { data: stats } = usePlatformStats();
  const { data: requests = [], isLoading: requestsLoading, refetch: refetchRequests } = useSubscriptionRequests();
  const { data: pendingBosses = [], isLoading: bossesLoading } = usePendingBosses();
  const { data: organizations = [], isLoading: organizationsLoading, refetch: refetchOrganizations } =
    useAdminOrganizations(deferredSearch);
  const { data: auditLogs = [], isLoading: auditLoading } = useAdminAuditLogs();
  const bossDecision = useBossDecision();

  const metrics = useMemo(
    () => [
      { label: '待处理', value: requests.length + pendingBosses.length, tone: requests.length ? ('warning' as const) : ('default' as const), detail: '会员与管理员申请' },
      { label: '付费企业', value: stats?.paid_organizations ?? 0, tone: 'success' as const, detail: '权益正常生效' },
      { label: '活跃企业', value: stats?.active_organizations ?? 0, detail: `共 ${stats?.total_organizations ?? 0} 家` },
      { label: '平台用户', value: stats?.total_users ?? 0, detail: `月活 ${stats?.monthly_active_users ?? 0}` },
      { label: 'AI 调用', value: (stats?.total_ai_calls_30d ?? 0).toLocaleString(), detail: '近 30 天' },
    ],
    [pendingBosses.length, requests.length, stats],
  );

  const decideBoss = async (userId: string, decision: 'approve' | 'reject') => {
    try {
      await bossDecision.mutateAsync({ userId, decision });
      toast.success(decision === 'approve' ? '管理员申请已批准' : '管理员申请已拒绝');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '操作失败');
    }
  };

  const logout = async () => {
    await signOut();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border bg-muted/40">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">平台管理</h1>
              <p className="text-xs text-muted-foreground">企业、会员与权限运营</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>返回业务系统</Button>
            <Button variant="ghost" size="icon" aria-label="退出登录" onClick={logout}><LogOut className="h-4 w-4" /></Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-7 px-5 py-7">
        <div>
          <p className="text-sm text-muted-foreground">平台运营总览</p>
          <h2 className="mt-1 text-2xl font-semibold">今天需要处理什么</h2>
        </div>

        <OperationalMetricStrip metrics={metrics} ariaLabel="平台运营指标" />

        <Tabs defaultValue="pending" className="space-y-6">
          <TabsList className="h-auto gap-1 bg-transparent p-0">
            <TabsTrigger value="pending" className="gap-2 data-[state=active]:bg-muted">
              <Clock3 className="h-4 w-4" />待处理
              {(requests.length + pendingBosses.length) > 0 && <Badge variant="destructive">{requests.length + pendingBosses.length}</Badge>}
            </TabsTrigger>
            <TabsTrigger value="organizations" className="gap-2 data-[state=active]:bg-muted"><Building2 className="h-4 w-4" />企业与会员</TabsTrigger>
            <TabsTrigger value="audit" className="gap-2 data-[state=active]:bg-muted"><FileClock className="h-4 w-4" />审计记录</TabsTrigger>
          </TabsList>

          <TabsContent value="pending" className="space-y-8">
            <section className="space-y-4">
              <SectionHeading
                title="会员开通与续期"
                description="核对申请套餐、有效期和用途，批准后对应企业即时生效。"
                action={<Button variant="ghost" size="sm" onClick={() => refetchRequests()}><RefreshCw className="mr-2 h-4 w-4" />刷新</Button>}
              />
              <AccessRequestQueue requests={requests} loading={requestsLoading} />
            </section>

            <section className="space-y-4">
              <SectionHeading title="管理员账号申请" description="只授予确需管理企业配置的负责人。" />
              <BossRequestTable
                items={pendingBosses}
                loading={bossesLoading}
                onDecision={decideBoss}
                pending={bossDecision.isPending}
              />
            </section>
          </TabsContent>

          <TabsContent value="organizations" className="space-y-4">
            <SectionHeading
              title="企业与会员"
              description="查看会员状态，调整套餐、精确到期日和使用配额。"
              action={
                <div className="flex gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input className="w-64 pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索企业" />
                  </div>
                  <Button variant="outline" size="icon" aria-label="刷新企业列表" onClick={() => refetchOrganizations()}><RefreshCw className="h-4 w-4" /></Button>
                </div>
              }
            />
            <OrganizationTable items={organizations} loading={organizationsLoading} onOpen={setSelectedOrganization} />
          </TabsContent>

          <TabsContent value="audit" className="space-y-4">
            <SectionHeading title="最近的高权限操作" description="会员、配额和企业状态的所有变更均保留操作者、时间与原因。" />
            <AuditLogTable items={auditLogs} loading={auditLoading} />
          </TabsContent>
        </Tabs>
      </main>

      <OrganizationAccessDialog organization={selectedOrganization} onOpenChange={(open) => !open && setSelectedOrganization(null)} />
    </div>
  );
}

function SectionHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><h3 className="font-semibold">{title}</h3><p className="mt-1 text-sm text-muted-foreground">{description}</p></div>
      {action}
    </div>
  );
}

function BossRequestTable({
  items,
  loading,
  pending,
  onDecision,
}: {
  items: PendingBoss[];
  loading: boolean;
  pending: boolean;
  onDecision: (userId: string, decision: 'approve' | 'reject') => void;
}) {
  if (loading) return <LoadingBlock />;
  if (!items.length) return <QuietEmpty icon={UserCheck} text="暂无管理员申请" />;
  return (
    <div className="divide-y border-y">
      {items.map((item) => (
        <div key={item.user_id} className="grid gap-4 py-4 md:grid-cols-[1fr_1fr_180px_auto] md:items-center">
          <div><p className="font-medium">{item.name}</p><p className="text-sm text-muted-foreground">{item.email}</p></div>
          <p className="text-sm">{item.organization_name || '未命名企业'}</p>
          <p className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString('zh-CN')}</p>
          <div className="flex gap-2 md:justify-end">
            <Button size="sm" disabled={pending} onClick={() => onDecision(item.user_id, 'approve')}><Check className="mr-1 h-4 w-4" />批准</Button>
            <Button size="sm" variant="outline" disabled={pending} onClick={() => onDecision(item.user_id, 'reject')}><X className="mr-1 h-4 w-4" />拒绝</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function OrganizationTable({ items, loading, onOpen }: { items: AdminOrganization[]; loading: boolean; onOpen: (item: AdminOrganization) => void }) {
  if (loading) return <LoadingBlock />;
  if (!items.length) return <QuietEmpty icon={Building2} text="没有匹配的企业" />;
  return (
    <div className="overflow-hidden border-y">
      <Table>
        <TableHeader><TableRow><TableHead>企业</TableHead><TableHead>会员</TableHead><TableHead>有效期</TableHead><TableHead>企业状态</TableHead><TableHead className="text-right">操作</TableHead></TableRow></TableHeader>
        <TableBody>
          {items.map((item) => {
            const access = ACCESS_STATE[item.access_state] ?? { label: item.access_state };
            return (
              <TableRow key={item.id}>
                <TableCell><p className="font-medium">{item.name}</p><p className="text-xs text-muted-foreground">{item.slug}</p></TableCell>
                <TableCell><div className="flex items-center gap-2"><span>{PLAN_NAMES[item.subscription?.plan ?? item.plan] ?? item.plan}</span><Badge variant="secondary" className={access.className}>{access.label}</Badge></div></TableCell>
                <TableCell className="text-sm tabular-nums text-muted-foreground">{item.subscription?.current_period_end ? new Date(item.subscription.current_period_end).toLocaleDateString('zh-CN') : '长期 / 未设置'}</TableCell>
                <TableCell><Badge variant="outline">{item.status === 'active' ? '正常' : '已停用'}</Badge></TableCell>
                <TableCell className="text-right"><Button variant="ghost" size="sm" onClick={() => onOpen(item)}><Eye className="mr-1 h-4 w-4" />管理</Button></TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function AuditLogTable({ items, loading }: { items: AuditLog[]; loading: boolean }) {
  if (loading) return <LoadingBlock />;
  if (!items.length) return <QuietEmpty icon={FileClock} text="暂无审计记录" />;
  return (
    <div className="divide-y border-y">
      {items.map((item) => (
        <div key={item.id} className="grid gap-2 py-3 text-sm md:grid-cols-[220px_1fr_180px] md:items-center">
          <p className="font-medium">{AUDIT_ACTIONS[item.action] ?? item.action}</p>
          <p className="truncate text-muted-foreground">企业 {item.organization_id ?? '-'} · 操作者 {item.user_id ?? '-'}</p>
          <p className="text-xs tabular-nums text-muted-foreground md:text-right">{new Date(item.created_at).toLocaleString('zh-CN')}</p>
        </div>
      ))}
    </div>
  );
}

function LoadingBlock() {
  return <div className="flex min-h-40 items-center justify-center border-y"><RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" /></div>;
}

function QuietEmpty({ icon: Icon, text }: { icon: ElementType; text: string }) {
  return <div className="flex min-h-40 flex-col items-center justify-center border-y text-muted-foreground"><Icon className="h-5 w-5" /><p className="mt-2 text-sm">{text}</p></div>;
}
