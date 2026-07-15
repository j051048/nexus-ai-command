import { useMemo, useState } from 'react';
import {
  Ban,
  CalendarMinus,
  CalendarPlus,
  CalendarClock,
  History,
  Loader2,
  RotateCcw,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  type AccessChange,
  type AdminOrganization,
  useAccessChangeAction,
  useAdjustOrganizationAccess,
  useAdminOrganization360,
  useSetOrganizationAccess,
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

export function Organization360Sheet({
  organization,
  onOpenChange,
  can,
}: Organization360SheetProps) {
  const { data, isLoading } = useAdminOrganization360(organization?.id);

  return (
    <Sheet open={Boolean(organization)} onOpenChange={onOpenChange}>
      <SheetContent className="w-[min(96vw,960px)] gap-0 p-0 sm:max-w-none">
        <SheetHeader className="border-b px-6 py-5 pr-14">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <SheetTitle>{data?.name ?? organization?.name ?? '企业详情'}</SheetTitle>
              <SheetDescription className="mt-1">
                {data?.slug ?? organization?.slug} · 会员变更对企业内所有用户统一生效
              </SheetDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">
                {PLAN_NAMES[data?.subscription?.plan ?? data?.plan ?? 'free']}
              </Badge>
              <Badge variant={data?.is_member ? 'secondary' : 'destructive'}>
                {data?.is_member ? '会员有效' : '非会员'}
              </Badge>
            </div>
          </div>
        </SheetHeader>

        {isLoading || !data ? (
          <div className="flex h-[70vh] items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <Tabs defaultValue="access" className="flex min-h-0 flex-1 flex-col">
            <TabsList className="h-12 justify-start rounded-none border-b bg-transparent px-6">
              <TabsTrigger value="access">会员设置</TabsTrigger>
              <TabsTrigger value="overview">企业概览</TabsTrigger>
              <TabsTrigger value="users">用户</TabsTrigger>
              <TabsTrigger value="commercial">商业记录</TabsTrigger>
              <TabsTrigger value="timeline">操作记录</TabsTrigger>
            </TabsList>
            <ScrollArea className="h-[calc(100vh-9.5rem)]">
              <div className="px-6 py-6">
                <TabsContent value="overview" className="mt-0">
                  <Overview data={data} />
                </TabsContent>
                <TabsContent value="access" className="mt-0">
                  <AccessAndQuota data={data} can={can} />
                </TabsContent>
                <TabsContent value="commercial" className="mt-0">
                  <CommercialRecords data={data} canEdit={can('manage_commercial')} />
                </TabsContent>
                <TabsContent value="users" className="mt-0">
                  <UserList data={data} />
                </TabsContent>
                <TabsContent value="timeline" className="mt-0">
                  <Timeline data={data} />
                </TabsContent>
              </div>
            </ScrollArea>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Overview({
  data,
}: {
  data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>;
}) {
  const metrics = [
    ['用户', data.user_count ?? data.users.length, `${data.active_users_30d} 人近 30 天活跃`],
    [
      'AI 请求',
      data.usage_30d.requests.toLocaleString(),
      `${data.usage_30d.tokens.toLocaleString()} tokens`,
    ],
    ['AI 成本', `$${data.usage_30d.cost_usd.toFixed(2)}`, '近 30 天'],
    [
      '会员到期',
      data.subscription?.current_period_end
        ? new Date(data.subscription.current_period_end).toLocaleDateString('zh-CN')
        : '长期',
      data.access_state,
    ],
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
          <Detail
            label="最近批准"
            value={
              data.subscription?.approved_at
                ? new Date(data.subscription.approved_at).toLocaleString('zh-CN')
                : '无记录'
            }
          />
          <Detail
            label="月度 Token 配额"
            value={(data.quotas?.monthly_token_limit ?? 0).toLocaleString()}
          />
          <Detail label="存储配额" value={`${data.quotas?.storage_limit_mb ?? 0} MB`} />
        </dl>
      </section>
    </div>
  );
}

function AccessAndQuota({
  data,
  can,
}: {
  data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>;
  can: (permission: string) => boolean;
}) {
  const [expiresAt, setExpiresAt] = useState(
    data.subscription?.current_period_end?.slice(0, 10) ?? ''
  );
  const [neverExpires, setNeverExpires] = useState(
    Boolean(data.is_member && !data.subscription?.current_period_end)
  );
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [quotas, setQuotas] = useState({
    monthly_token_limit: data.quotas?.monthly_token_limit ?? 0,
    monthly_api_call_limit: data.quotas?.monthly_api_call_limit ?? 0,
    storage_limit_mb: data.quotas?.storage_limit_mb ?? 0,
  });
  const setAccess = useSetOrganizationAccess();
  const adjustAccess = useAdjustOrganizationAccess();
  const updateQuotas = useUpdateOrganizationQuotas();

  const membershipPlan =
    data.subscription?.plan && data.subscription.plan !== 'free'
      ? data.subscription.plan
      : 'enterprise';

  const submitAccess = async () => {
    if (!neverExpires && !expiresAt) return toast.error('请选择会员到期日');
    try {
      await setAccess.mutateAsync({
        orgId: data.id,
        plan: membershipPlan,
        expires_at: neverExpires ? null : new Date(`${expiresAt}T23:59:59`).toISOString(),
        reason: '平台管理员手动设置会员到期时间',
      });
      toast.success('会员已开通，到期时间已保存');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会员变更失败');
    }
  };

  const adjustDays = async (days: number) => {
    try {
      await adjustAccess.mutateAsync({
        orgId: data.id,
        days,
        reason: `平台管理员${days > 0 ? '增加' : '减少'} ${Math.abs(days)} 天会员期限`,
      });
      toast.success(days > 0 ? `会员期限已增加 ${days} 天` : `会员期限已减少 ${Math.abs(days)} 天`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会员期限调整失败');
    }
  };

  const revokeMembership = async () => {
    try {
      await setAccess.mutateAsync({
        orgId: data.id,
        plan: 'free',
        expires_at: null,
        reason: '平台管理员手动撤销企业会员',
      });
      setConfirmRevoke(false);
      toast.success('企业会员已撤销');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '撤销会员失败');
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
      <section className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b pb-5">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold">{data.is_member ? '会员已生效' : '尚未开通会员'}</h3>
              <Badge variant={data.is_member ? 'secondary' : 'outline'}>
                {data.is_member ? '全部功能可用' : '部分功能受限'}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {data.is_member
                ? '企业内所有用户均可使用完整功能，且不会显示会员广告或体验提醒。'
                : '开通后会立即解除企业内所有用户的功能限制和会员提醒。'}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">当前到期日</p>
            <p className="mt-1 font-medium tabular-nums">
              {data.subscription?.current_period_end
                ? new Date(data.subscription.current_period_end).toLocaleDateString('zh-CN')
                : data.is_member
                  ? '长期有效'
                  : '未设置'}
            </p>
          </div>
        </div>

        {can('manage_memberships') && (
          <>
            <div>
              <Label>快捷调整</Label>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() => adjustDays(30)}
                  disabled={adjustAccess.isPending}
                >
                  <CalendarPlus className="mr-2 h-4 w-4" />
                  增加 30 天
                </Button>
                <Button
                  variant="outline"
                  onClick={() => adjustDays(365)}
                  disabled={adjustAccess.isPending}
                >
                  <CalendarPlus className="mr-2 h-4 w-4" />
                  增加 1 年
                </Button>
                {data.is_member && data.subscription?.current_period_end && (
                  <Button
                    variant="outline"
                    onClick={() => adjustDays(-30)}
                    disabled={adjustAccess.isPending}
                  >
                    <CalendarMinus className="mr-2 h-4 w-4" />
                    减少 30 天
                  </Button>
                )}
              </div>
            </div>

            <div className="grid gap-4 border-y py-5 sm:grid-cols-[1fr_auto] sm:items-end">
              <Field label="手动设置到期日">
                <Input
                  type="date"
                  value={expiresAt}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={(event) => setExpiresAt(event.target.value)}
                  disabled={neverExpires}
                />
              </Field>
              <Button onClick={submitAccess} disabled={setAccess.isPending}>
                {data.is_member ? '保存到期时间' : '开通企业会员'}
              </Button>
              <label className="flex items-center gap-2 text-sm text-muted-foreground sm:col-span-2">
                <input
                  type="checkbox"
                  checked={neverExpires}
                  onChange={(event) => setNeverExpires(event.target.checked)}
                  className="h-4 w-4 rounded border-input"
                />
                长期有效，不设置到期日
              </label>
            </div>

            {data.is_member && (
              <Button
                variant="ghost"
                className="text-destructive hover:text-destructive"
                onClick={() => setConfirmRevoke(true)}
              >
                <Ban className="mr-2 h-4 w-4" />
                撤销企业会员
              </Button>
            )}
          </>
        )}
      </section>

      <details className="group border-y py-4">
        <summary className="cursor-pointer text-sm font-medium">
          高级设置：使用配额与权益记录
        </summary>
        <div className="mt-6 space-y-8">
          <section>
            <h3 className="text-sm font-medium">使用配额</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {Object.entries(quotas).map(([key, value]) => (
                <Field
                  key={key}
                  label={
                    key === 'monthly_token_limit'
                      ? '月度 Token'
                      : key === 'monthly_api_call_limit'
                        ? '月度 API'
                        : '存储 MB'
                  }
                >
                  <Input
                    type="number"
                    min={0}
                    value={value}
                    onChange={(event) =>
                      setQuotas((current) => ({ ...current, [key]: Number(event.target.value) }))
                    }
                  />
                </Field>
              ))}
            </div>
            {can('manage_quotas') && (
              <Button
                variant="outline"
                className="mt-4"
                onClick={submitQuotas}
                disabled={updateQuotas.isPending}
              >
                更新配额
              </Button>
            )}
          </section>
          <AccessHistory changes={data.access_versions} canRollback={can('manage_memberships')} />
        </div>
      </details>

      <Dialog open={confirmRevoke} onOpenChange={setConfirmRevoke}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>撤销 {data.name} 的企业会员？</DialogTitle>
          </DialogHeader>
          <p className="text-sm leading-6 text-muted-foreground">
            撤销后，该企业所有用户会看到会员提醒，部分高级功能将立即受限。历史数据不会删除。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmRevoke(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={revokeMembership} disabled={setAccess.isPending}>
              确认撤销
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AccessHistory({
  changes,
  canRollback,
}: {
  changes: AccessChange[];
  canRollback: boolean;
}) {
  const [action, setAction] = useState<{ item: AccessChange; type: 'cancel' | 'rollback' } | null>(
    null
  );
  const [reason, setReason] = useState('');
  const mutation = useAccessChangeAction();
  const submit = async () => {
    if (!action || reason.trim().length < 2) return toast.error('请填写操作原因');
    try {
      await mutation.mutateAsync({
        changeId: action.item.id,
        action: action.type,
        reason: reason.trim(),
      });
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
        {changes.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">暂无权益变更记录</p>
        )}
        {changes.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div>
              <p className="text-sm font-medium">
                {PLAN_NAMES[item.next_snapshot.plan] ?? item.next_snapshot.plan} ·{' '}
                {item.change_status}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {item.reason} · {new Date(item.effective_at).toLocaleString('zh-CN')}
              </p>
            </div>
            {canRollback && item.change_status === 'scheduled' && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setReason('');
                  setAction({ item, type: 'cancel' });
                }}
              >
                取消预约
              </Button>
            )}
            {canRollback && item.change_status === 'applied' && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setReason('');
                  setAction({ item, type: 'rollback' });
                }}
              >
                <RotateCcw className="mr-1 h-3.5 w-3.5" />
                回滚
              </Button>
            )}
          </div>
        ))}
      </div>
      <Dialog open={Boolean(action)} onOpenChange={(open) => !open && setAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {action?.type === 'rollback' ? '回滚会员状态' : '取消预约变更'}
            </DialogTitle>
          </DialogHeader>
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="说明本次操作原因"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAction(null)}>
              取消
            </Button>
            <Button onClick={submit} disabled={mutation.isPending}>
              确认
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function CommercialRecords({
  data,
  canEdit,
}: {
  data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>;
  canEdit: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    order_number: '',
    contract_number: '',
    amount: '',
    payment_status: 'pending',
    due_at: '',
    notes: '',
  });
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
      <div className="flex items-end justify-between">
        <div>
          <h3 className="text-sm font-medium">合同、回款与发票</h3>
          <p className="mt-1 text-sm text-muted-foreground">商业凭证与会员权益分开记录。</p>
        </div>
        {canEdit && (
          <Button size="sm" onClick={() => setOpen(true)}>
            新增记录
          </Button>
        )}
      </div>
      <div className="mt-4 divide-y border-y">
        {data.commercial_records.length === 0 && (
          <p className="py-10 text-center text-sm text-muted-foreground">暂无商业记录</p>
        )}
        {data.commercial_records.map((item) => (
          <div
            key={item.id}
            className="grid gap-2 py-4 sm:grid-cols-[1fr_150px_120px] sm:items-center"
          >
            <div>
              <p className="font-medium">{item.order_number}</p>
              <p className="text-xs text-muted-foreground">
                合同 {item.contract_number || '未关联'} · 发票 {item.invoice_status}
              </p>
            </div>
            <p className="font-medium tabular-nums">
              ¥{((item.amount_cents - item.discount_cents) / 100).toLocaleString()}
            </p>
            <Badge variant="outline" className="w-fit">
              {item.payment_status}
            </Badge>
          </div>
        ))}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增商业记录</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="订单编号">
              <Input
                value={form.order_number}
                onChange={(e) => setForm({ ...form, order_number: e.target.value })}
              />
            </Field>
            <Field label="合同编号">
              <Input
                value={form.contract_number}
                onChange={(e) => setForm({ ...form, contract_number: e.target.value })}
              />
            </Field>
            <Field label="实收前金额（元）">
              <Input
                type="number"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </Field>
            <Field label="回款状态">
              <Select
                value={form.payment_status}
                onValueChange={(value) => setForm({ ...form, payment_status: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {['pending', 'partial', 'paid', 'overdue', 'waived'].map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="应收日期">
              <Input
                type="date"
                value={form.due_at}
                onChange={(e) => setForm({ ...form, due_at: e.target.value })}
              />
            </Field>
            <Field label="备注">
              <Input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={save} disabled={mutation.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function UserList({
  data,
}: {
  data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>;
}) {
  return (
    <section>
      <h3 className="text-sm font-medium">企业用户</h3>
      <div className="mt-3 divide-y border-y">
        {data.users.map((user) => (
          <div key={user.id} className="grid gap-2 py-3 sm:grid-cols-[1fr_120px_180px]">
            <div>
              <p className="text-sm font-medium">{user.full_name || user.email || user.id}</p>
              <p className="text-xs text-muted-foreground">{user.email}</p>
            </div>
            <Badge variant="outline" className="w-fit">
              {user.role}
            </Badge>
            <p className="text-xs text-muted-foreground">
              {user.last_active_at
                ? `最近活跃 ${new Date(user.last_active_at).toLocaleString('zh-CN')}`
                : '暂无活跃记录'}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Timeline({
  data,
}: {
  data: NonNullable<ReturnType<typeof useAdminOrganization360>['data']>;
}) {
  const timeline = useMemo(
    () =>
      [
        ...data.audit_timeline.map((item) => ({
          id: item.id,
          title: item.action,
          detail: String(item.details?.reason ?? ''),
          at: item.created_at,
          icon: History,
        })),
        ...data.access_requests.map((item) => ({
          id: item.id,
          title: `会员申请 · ${item.status}`,
          detail: item.note ?? '',
          at: item.created_at,
          icon: CalendarClock,
        })),
      ].sort((a, b) => b.at.localeCompare(a.at)),
    [data.access_requests, data.audit_timeline]
  );
  return (
    <section>
      <h3 className="text-sm font-medium">操作时间线</h3>
      <div className="mt-4 space-y-0">
        {timeline.map((item) => (
          <div
            key={`${item.title}:${item.id}`}
            className="grid grid-cols-[28px_1fr] gap-3 border-l pb-5 pl-4"
          >
            <item.icon className="-ml-[30px] h-4 w-4 bg-background text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{item.title}</p>
              {item.detail && <p className="mt-1 text-sm text-muted-foreground">{item.detail}</p>}
              <p className="mt-1 text-xs text-muted-foreground">
                {new Date(item.at).toLocaleString('zh-CN')}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  );
}
