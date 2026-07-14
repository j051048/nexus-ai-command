import { useMemo, useState } from 'react';
import {
  CalendarClock,
  History,
  Loader2,
  RotateCcw,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  type AccessChange,
  type AdminOrganization,
  useAccessChangeAction,
  useAdminOrganization360,
  useOrganizationStatusAction,
  useScheduleOrganizationAccess,
  useUpdateOrganizationQuotas,
  useUpsertCommercialRecord,
} from '@/hooks/useSuperAdminConsole';

const PLAN_NAMES: Record<string, string> = {
  free: '未开通',
  starter: '团队版',
  professional: '专业版',
  enterprise: '企业版',
};

interface Organization360SheetProps {
  organization: AdminOrganization | null;
  onOpenChange: (open: boolean) => void;
  can: (permission: string) => boolean;
}

export function Organization360Sheet({ organization, onOpenChange, can }: Organization360SheetProps) {
  const { data, isLoading } = useAdminOrganization360(organization?.id);
  const statusAction = useOrganizationStatusAction();

  const toggleStatus = async () => {
    if (!organization) return;
    const action = organization.status === 'active' ? 'suspend' : 'unsuspend';
    try {
      await statusAction.mutateAsync({
        orgId: organization.id,
        action,
        reason: action === 'suspend' ? '平台运营人工停用' : undefined,
      });
      toast.success(action === 'suspend' ? '企业已停用' : '企业已恢复');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '企业状态更新失败');
    }
  };

  return (
    <Sheet open={Boolean(organization)} onOpenChange={onOpenChange}>
      <SheetContent className="w-[min(96vw,960px)] gap-0 p-0 sm:max-w-none">
        <SheetHeader className="border-b px-6 py-5 pr-14">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <SheetTitle>{data?.name ?? organization?.name ?? '企业详情'}</SheetTitle>
              <SheetDescription className="mt-1">
                {data?.slug ?? organization?.slug} · 企业、权益、成本与商业凭证
              </SheetDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{PLAN_NAMES[data?.subscription?.plan ?? data?.plan ?? 'free']}</Badge>
              <Badge variant={data?.status === 'active' ? 'secondary' : 'destructive'}>
                {data?.status === 'active' ? '正常' : '已停用'}
              </Badge>
              {can('manage_organizations') && (
                <Button variant="outline" size="sm" onClick={toggleStatus} disabled={statusAction.isPending}>
                  {data?.status === 'active' ? '停用' : '恢复'}
                </Button>
              )}
            </div>
          </div>
        </SheetHeader>

        {isLoading || !data ? (
          <div className="flex h-[70vh] items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>
        ) : (
          <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
            <TabsList className="h-12 justify-start rounded-none border-b bg-transparent px-6">
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="access">会员与配额</TabsTrigger>
              <TabsTrigger value="commercial">商业记录</TabsTrigger>
              <TabsTrigger value="users">用户</TabsTrigger>
              <TabsTrigger value="timeline">时间线</TabsTrigger>
            </TabsList>
            <ScrollArea className="h-[calc(100vh-9.5rem)]">
              <div className="px-6 py-6">
                <TabsContent value="overview" className="mt-0"><Overview data={data} /></TabsContent>
                <TabsContent value="access" className="mt-0">
                  <AccessAndQuota data={data} can={can} />
                </TabsContent>
                <TabsContent value="commercial" className="mt-0">
                  <CommercialRecords data={data} canEdit={can('manage_commercial')} />
                </TabsContent>
                <TabsContent value="users" className="mt-0"><UserList data={data} /></TabsContent>
                <TabsContent value="timeline" className="mt-0"><Timeline data={data} /></TabsContent>
              </div>
            </ScrollArea>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Overview({ data }: { data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']> }) {
  const metrics = [
    ['用户', data.user_count ?? data.users.length, `${data.active_users_30d} 人近 30 天活跃`],
    ['AI 请求', data.usage_30d.requests.toLocaleString(), `${data.usage_30d.tokens.toLocaleString()} tokens`],
    ['AI 成本', `$${data.usage_30d.cost_usd.toFixed(2)}`, '近 30 天'],
    ['会员到期', data.subscription?.current_period_end ? new Date(data.subscription.current_period_end).toLocaleDateString('zh-CN') : '长期', data.access_state],
  ];
  return (
    <div className="space-y-8">
      <section>
        <h3 className="text-sm font-medium">运营摘要</h3>
        <div className="mt-3 grid border-y sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map(([label, value, detail], index) => (
            <div key={String(label)} className={`py-4 sm:px-4 ${index > 0 ? 'sm:border-l' : ''}`}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
              <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
            </div>
          ))}
        </div>
      </section>
      <section>
        <h3 className="text-sm font-medium">当前状态</h3>
        <dl className="mt-3 grid gap-x-8 gap-y-4 border-y py-4 sm:grid-cols-2">
          <Detail label="权益来源" value={data.subscription?.access_source ?? '未配置'} />
          <Detail label="最近批准" value={data.subscription?.approved_at ? new Date(data.subscription.approved_at).toLocaleString('zh-CN') : '无记录'} />
          <Detail label="月度 Token 配额" value={(data.quotas?.monthly_token_limit ?? 0).toLocaleString()} />
          <Detail label="存储配额" value={`${data.quotas?.storage_limit_mb ?? 0} MB`} />
        </dl>
      </section>
    </div>
  );
}

function AccessAndQuota({ data, can }: { data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>; can: (permission: string) => boolean }) {
  const [plan, setPlan] = useState(data.subscription?.plan ?? data.plan ?? 'professional');
  const [expiresAt, setExpiresAt] = useState(data.subscription?.current_period_end?.slice(0, 10) ?? '');
  const [effectiveAt, setEffectiveAt] = useState('');
  const [reason, setReason] = useState('');
  const [quotas, setQuotas] = useState({
    monthly_token_limit: data.quotas?.monthly_token_limit ?? 0,
    monthly_api_call_limit: data.quotas?.monthly_api_call_limit ?? 0,
    storage_limit_mb: data.quotas?.storage_limit_mb ?? 0,
  });
  const schedule = useScheduleOrganizationAccess();
  const updateQuotas = useUpdateOrganizationQuotas();

  const submitAccess = async () => {
    if (reason.trim().length < 2) return toast.error('请填写变更原因');
    try {
      await schedule.mutateAsync({
        orgId: data.id,
        plan,
        expires_at: expiresAt ? new Date(`${expiresAt}T23:59:59`).toISOString() : null,
        effective_at: effectiveAt ? new Date(effectiveAt).toISOString() : null,
        reason: reason.trim(),
      });
      toast.success(effectiveAt ? '会员变更已预约' : '会员权益已更新');
      setReason('');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会员变更失败');
    }
  };

  const submitQuotas = async () => {
    try {
      await updateQuotas.mutateAsync({ orgId: data.id, ...quotas, reason: '平台运营调整配额' });
      toast.success('配额已更新');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '配额更新失败');
    }
  };

  return (
    <div className="space-y-8">
      <section>
        <h3 className="text-sm font-medium">会员变更</h3>
        <p className="mt-1 text-sm text-muted-foreground">留空生效时间将立即执行；留空有效期表示长期授权。</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="套餐"><Select value={plan} onValueChange={setPlan}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(PLAN_NAMES).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></Field>
          <Field label="有效期至"><Input type="date" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} /></Field>
          <Field label="预约生效"><Input type="datetime-local" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} /></Field>
          <Field label="变更原因"><Input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="合同确认、续期或运营调整" /></Field>
        </div>
        {can('manage_memberships') && <Button className="mt-4" onClick={submitAccess} disabled={schedule.isPending}>{effectiveAt ? '保存预约' : '立即生效'}</Button>}
      </section>
      <section>
        <h3 className="text-sm font-medium">使用配额</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {Object.entries(quotas).map(([key, value]) => (
            <Field key={key} label={key === 'monthly_token_limit' ? '月度 Token' : key === 'monthly_api_call_limit' ? '月度 API' : '存储 MB'}>
              <Input type="number" min={0} value={value} onChange={(event) => setQuotas((current) => ({ ...current, [key]: Number(event.target.value) }))} />
            </Field>
          ))}
        </div>
        {can('manage_quotas') && <Button variant="outline" className="mt-4" onClick={submitQuotas} disabled={updateQuotas.isPending}>更新配额</Button>}
      </section>
      <AccessHistory changes={data.access_versions} canRollback={can('manage_memberships')} />
    </div>
  );
}

function AccessHistory({ changes, canRollback }: { changes: AccessChange[]; canRollback: boolean }) {
  const [action, setAction] = useState<{ item: AccessChange; type: 'cancel' | 'rollback' } | null>(null);
  const [reason, setReason] = useState('');
  const mutation = useAccessChangeAction();
  const submit = async () => {
    if (!action || reason.trim().length < 2) return toast.error('请填写操作原因');
    try {
      await mutation.mutateAsync({ changeId: action.item.id, action: action.type, reason: reason.trim() });
      toast.success(action.type === 'rollback' ? '会员状态已回滚' : '预约变更已取消');
      setAction(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '操作失败');
    }
  };
  return (
    <section>
      <h3 className="text-sm font-medium">权益版本</h3>
      <div className="mt-3 divide-y border-y">
        {changes.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">暂无权益变更记录</p>}
        {changes.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div><p className="text-sm font-medium">{PLAN_NAMES[item.next_snapshot.plan] ?? item.next_snapshot.plan} · {item.change_status}</p><p className="mt-1 text-xs text-muted-foreground">{item.reason} · {new Date(item.effective_at).toLocaleString('zh-CN')}</p></div>
            {canRollback && item.change_status === 'scheduled' && <Button size="sm" variant="ghost" onClick={() => { setReason(''); setAction({ item, type: 'cancel' }); }}>取消预约</Button>}
            {canRollback && item.change_status === 'applied' && <Button size="sm" variant="ghost" onClick={() => { setReason(''); setAction({ item, type: 'rollback' }); }}><RotateCcw className="mr-1 h-3.5 w-3.5" />回滚</Button>}
          </div>
        ))}
      </div>
      <Dialog open={Boolean(action)} onOpenChange={(open) => !open && setAction(null)}>
        <DialogContent><DialogHeader><DialogTitle>{action?.type === 'rollback' ? '回滚会员状态' : '取消预约变更'}</DialogTitle></DialogHeader><Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="说明本次操作原因" /><DialogFooter><Button variant="outline" onClick={() => setAction(null)}>取消</Button><Button onClick={submit} disabled={mutation.isPending}>确认</Button></DialogFooter></DialogContent>
      </Dialog>
    </section>
  );
}

function CommercialRecords({ data, canEdit }: { data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>; canEdit: boolean }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ order_number: '', contract_number: '', amount: '', payment_status: 'pending', due_at: '', notes: '' });
  const mutation = useUpsertCommercialRecord();
  const save = async () => {
    if (!form.order_number.trim()) return toast.error('请填写订单编号');
    try {
      await mutation.mutateAsync({
        org_id: data.id,
        order_number: form.order_number.trim(),
        contract_number: form.contract_number || null,
        amount_cents: Math.round(Number(form.amount || 0) * 100),
        payment_status: form.payment_status,
        due_at: form.due_at ? new Date(`${form.due_at}T23:59:59`).toISOString() : null,
        invoice_status: 'none',
        discount_cents: 0,
        currency: 'CNY',
        gifted_days: 0,
        notes: form.notes || null,
      });
      toast.success('商业记录已保存');
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '保存失败');
    }
  };
  return (
    <section>
      <div className="flex items-end justify-between"><div><h3 className="text-sm font-medium">合同、回款与发票</h3><p className="mt-1 text-sm text-muted-foreground">商业凭证与会员权益分开记录。</p></div>{canEdit && <Button size="sm" onClick={() => setOpen(true)}>新增记录</Button>}</div>
      <div className="mt-4 divide-y border-y">
        {data.commercial_records.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">暂无商业记录</p>}
        {data.commercial_records.map((item) => (
          <div key={item.id} className="grid gap-2 py-4 sm:grid-cols-[1fr_150px_120px] sm:items-center"><div><p className="font-medium">{item.order_number}</p><p className="text-xs text-muted-foreground">合同 {item.contract_number || '未关联'} · 发票 {item.invoice_status}</p></div><p className="font-medium tabular-nums">¥{((item.amount_cents - item.discount_cents) / 100).toLocaleString()}</p><Badge variant="outline" className="w-fit">{item.payment_status}</Badge></div>
        ))}
      </div>
      <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>新增商业记录</DialogTitle></DialogHeader><div className="grid gap-4 sm:grid-cols-2"><Field label="订单编号"><Input value={form.order_number} onChange={(e) => setForm({ ...form, order_number: e.target.value })} /></Field><Field label="合同编号"><Input value={form.contract_number} onChange={(e) => setForm({ ...form, contract_number: e.target.value })} /></Field><Field label="实收前金额（元）"><Input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field><Field label="回款状态"><Select value={form.payment_status} onValueChange={(value) => setForm({ ...form, payment_status: value })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{['pending', 'partial', 'paid', 'overdue', 'waived'].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent></Select></Field><Field label="应收日期"><Input type="date" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} /></Field><Field label="备注"><Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field></div><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>取消</Button><Button onClick={save} disabled={mutation.isPending}>保存</Button></DialogFooter></DialogContent></Dialog>
    </section>
  );
}

function UserList({ data }: { data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']> }) {
  return <section><h3 className="text-sm font-medium">企业用户</h3><div className="mt-3 divide-y border-y">{data.users.map((user) => <div key={user.id} className="grid gap-2 py-3 sm:grid-cols-[1fr_120px_180px]"><div><p className="text-sm font-medium">{user.full_name || user.email || user.id}</p><p className="text-xs text-muted-foreground">{user.email}</p></div><Badge variant="outline" className="w-fit">{user.role}</Badge><p className="text-xs text-muted-foreground">{user.last_active_at ? `最近活跃 ${new Date(user.last_active_at).toLocaleString('zh-CN')}` : '暂无活跃记录'}</p></div>)}</div></section>;
}

function Timeline({ data }: { data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']> }) {
  const timeline = useMemo(() => [
    ...data.audit_timeline.map((item) => ({ id: item.id, title: item.action, detail: String(item.details?.reason ?? ''), at: item.created_at, icon: History })),
    ...data.access_requests.map((item) => ({ id: item.id, title: `会员申请 · ${item.status}`, detail: item.note ?? '', at: item.created_at, icon: CalendarClock })),
  ].sort((a, b) => b.at.localeCompare(a.at)), [data.access_requests, data.audit_timeline]);
  return <section><h3 className="text-sm font-medium">操作时间线</h3><div className="mt-4 space-y-0">{timeline.map((item) => <div key={`${item.title}:${item.id}`} className="grid grid-cols-[28px_1fr] gap-3 border-l pb-5 pl-4"><item.icon className="-ml-[30px] h-4 w-4 bg-background text-muted-foreground" /><div><p className="text-sm font-medium">{item.title}</p>{item.detail && <p className="mt-1 text-sm text-muted-foreground">{item.detail}</p>}<p className="mt-1 text-xs text-muted-foreground">{new Date(item.at).toLocaleString('zh-CN')}</p></div></div>)}</div></section>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="grid gap-2"><Label>{label}</Label>{children}</div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs text-muted-foreground">{label}</dt><dd className="mt-1 text-sm font-medium">{value}</dd></div>;
}
