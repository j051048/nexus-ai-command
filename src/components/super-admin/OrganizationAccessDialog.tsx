import { useEffect, useState } from 'react';
import { AlertTriangle, Loader2, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  type AdminOrganization,
  useAdminOrganization,
  useDeleteOrganization,
  useOrganizationStatusAction,
  useSetOrganizationAccess,
  useUpdateOrganizationQuotas,
} from '@/hooks/useSuperAdminConsole';

function toDateInput(value?: string | null): string {
  return value ? new Date(value).toISOString().slice(0, 10) : '';
}

export function OrganizationAccessDialog({
  organization,
  onOpenChange,
}: {
  organization: AdminOrganization | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: detail, isLoading } = useAdminOrganization(organization?.id);
  const activeOrg = detail ?? organization;
  const [plan, setPlan] = useState('professional');
  const [expiresAt, setExpiresAt] = useState('');
  const [neverExpires, setNeverExpires] = useState(false);
  const [accessReason, setAccessReason] = useState('');
  const [tokenLimit, setTokenLimit] = useState('');
  const [apiLimit, setApiLimit] = useState('');
  const [storageLimit, setStorageLimit] = useState('');
  const [quotaReason, setQuotaReason] = useState('');
  const [statusReason, setStatusReason] = useState('');
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const setAccess = useSetOrganizationAccess();
  const updateQuotas = useUpdateOrganizationQuotas();
  const statusAction = useOrganizationStatusAction();
  const deleteOrganization = useDeleteOrganization();

  useEffect(() => {
    if (!activeOrg) return;
    setPlan(activeOrg.subscription?.plan ?? activeOrg.plan ?? 'professional');
    setExpiresAt(toDateInput(activeOrg.subscription?.current_period_end));
    setNeverExpires(!activeOrg.subscription?.current_period_end && activeOrg.access_state === 'active');
    setTokenLimit(String(activeOrg.quotas?.monthly_token_limit ?? ''));
    setApiLimit(String(activeOrg.quotas?.monthly_api_call_limit ?? ''));
    setStorageLimit(String(activeOrg.quotas?.storage_limit_mb ?? ''));
    setAccessReason('');
    setQuotaReason('');
    setStatusReason('');
    setDeleteConfirmation('');
  }, [activeOrg]);

  const saveAccess = async () => {
    if (!activeOrg || accessReason.trim().length < 2 || (!neverExpires && !expiresAt)) {
      toast.error('请填写有效期和变更原因');
      return;
    }
    try {
      await setAccess.mutateAsync({
        orgId: activeOrg.id,
        plan,
        expires_at: neverExpires ? null : new Date(`${expiresAt}T23:59:59`).toISOString(),
        reason: accessReason.trim(),
      });
      toast.success('会员权益已更新，客户端将在两分钟内自动刷新');
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会员权益更新失败');
    }
  };

  const saveQuotas = async () => {
    if (!activeOrg || quotaReason.trim().length < 2 || (!tokenLimit && !apiLimit && !storageLimit)) {
      toast.error('请至少填写一项配额和调整原因');
      return;
    }
    try {
      await updateQuotas.mutateAsync({
        orgId: activeOrg.id,
        reason: quotaReason.trim(),
        monthly_token_limit: tokenLimit ? Number(tokenLimit) : undefined,
        monthly_api_call_limit: apiLimit ? Number(apiLimit) : undefined,
        storage_limit_mb: storageLimit ? Number(storageLimit) : undefined,
      });
      toast.success('配额已更新');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '配额更新失败');
    }
  };

  const changeStatus = async () => {
    if (!activeOrg || (activeOrg.status === 'active' && statusReason.trim().length < 2)) {
      toast.error('请填写停用原因');
      return;
    }
    const action = activeOrg.status === 'active' ? 'suspend' : 'unsuspend';
    try {
      await statusAction.mutateAsync({ orgId: activeOrg.id, action, reason: statusReason.trim() });
      toast.success(action === 'suspend' ? '企业已停用' : '企业已恢复');
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '企业状态更新失败');
    }
  };

  const removeOrganization = async () => {
    if (!activeOrg || deleteConfirmation !== activeOrg.name) {
      toast.error('企业名称不匹配');
      return;
    }
    try {
      await deleteOrganization.mutateAsync({ orgId: activeOrg.id });
      toast.success('企业已删除');
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '企业删除失败');
    }
  };

  return (
    <Dialog open={Boolean(organization)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{activeOrg?.name ?? '企业管理'}</DialogTitle>
          <DialogDescription>
            {activeOrg?.slug} · {activeOrg?.user_count ?? '-'} 位成员 · 近 30 天 {activeOrg?.ai_calls_30d ?? '-'} 次 AI 调用
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>
        ) : activeOrg ? (
          <Tabs defaultValue="access" className="space-y-5">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="access">会员权益</TabsTrigger>
              <TabsTrigger value="quota">使用配额</TabsTrigger>
              <TabsTrigger value="risk">状态与风险</TabsTrigger>
            </TabsList>

            <TabsContent value="access" className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="admin-plan">套餐</Label>
                  <Select value={plan} onValueChange={setPlan}>
                    <SelectTrigger id="admin-plan"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="free">未开通</SelectItem>
                      <SelectItem value="starter">团队版</SelectItem>
                      <SelectItem value="professional">专业版</SelectItem>
                      <SelectItem value="enterprise">企业版</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="admin-expiry">有效期至</Label>
                  <Input
                    id="admin-expiry"
                    type="date"
                    value={expiresAt}
                    onChange={(event) => setExpiresAt(event.target.value)}
                    disabled={neverExpires}
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={neverExpires} onCheckedChange={(checked) => setNeverExpires(Boolean(checked))} />
                长期有效，不设置到期日
              </label>
              <div className="grid gap-2">
                <Label htmlFor="access-reason">变更原因</Label>
                <Textarea id="access-reason" value={accessReason} onChange={(event) => setAccessReason(event.target.value)} rows={3} />
              </div>
              <div className="flex justify-end">
                <Button onClick={saveAccess} disabled={setAccess.isPending}><Save className="mr-2 h-4 w-4" />保存并即时生效</Button>
              </div>
            </TabsContent>

            <TabsContent value="quota" className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-3">
                <NumberField label="月度 Token" value={tokenLimit} onChange={setTokenLimit} />
                <NumberField label="月度 API 调用" value={apiLimit} onChange={setApiLimit} />
                <NumberField label="存储空间 MB" value={storageLimit} onChange={setStorageLimit} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="quota-reason">调整原因</Label>
                <Textarea id="quota-reason" value={quotaReason} onChange={(event) => setQuotaReason(event.target.value)} rows={3} />
              </div>
              <div className="flex justify-end"><Button onClick={saveQuotas}>保存配额</Button></div>
            </TabsContent>

            <TabsContent value="risk" className="space-y-6">
              <section className="space-y-3 border-y py-4">
                <div>
                  <h3 className="font-medium">{activeOrg.status === 'active' ? '停用企业' : '恢复企业'}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">停用会立即影响该企业所有成员，请先核对原因。</p>
                </div>
                {activeOrg.status === 'active' && (
                  <Input value={statusReason} onChange={(event) => setStatusReason(event.target.value)} placeholder="停用原因" />
                )}
                <Button variant={activeOrg.status === 'active' ? 'destructive' : 'default'} onClick={changeStatus}>
                  {activeOrg.status === 'active' ? '确认停用' : '恢复企业'}
                </Button>
              </section>
              {activeOrg.slug !== 'default-org' && (
                <section className="space-y-3 border-b pb-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                    <div>
                      <h3 className="font-medium">永久删除企业</h3>
                      <p className="mt-1 text-sm text-muted-foreground">输入“{activeOrg.name}”后才能执行，数据不可恢复。</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Input value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} />
                    <Button variant="destructive" onClick={removeOrganization}><Trash2 className="mr-2 h-4 w-4" />删除</Button>
                  </div>
                </section>
              )}
            </TabsContent>
          </Tabs>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const id = `quota-${label}`;
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}
