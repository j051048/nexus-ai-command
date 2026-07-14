import { useState } from 'react';
import { Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useAdminAssignments, useSetAdminAssignment } from '@/hooks/useSuperAdminConsole';

const ROLE_NAMES: Record<string, string> = {
  platform_owner: '平台所有者',
  billing_operator: '会员运营',
  support_operator: '客户支持',
  security_auditor: '安全审计',
  finance_reviewer: '财务复核',
};

export function AdminRolesPanel() {
  const { data = [], isLoading } = useAdminAssignments();
  const mutation = useSetAdminAssignment();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ user_id: '', admin_role: 'support_operator', active: true });

  const save = async () => {
    if (!form.user_id.trim()) return toast.error('请填写平台管理员用户 ID');
    try {
      await mutation.mutateAsync({ ...form, user_id: form.user_id.trim(), permissions: [] });
      toast.success('管理员职责已更新');
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '管理员职责更新失败');
    }
  };

  if (isLoading) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  return (
    <section className="space-y-5">
      <div className="flex items-end justify-between gap-4"><div><h3 className="font-semibold">平台管理员职责</h3><p className="mt-1 text-sm text-muted-foreground">会员、客服、财务和审计岗位按最小权限分工。</p></div><Button size="sm" onClick={() => { setForm({ user_id: '', admin_role: 'support_operator', active: true }); setOpen(true); }}>分配职责</Button></div>
      <div className="divide-y border-y">
        {data.length === 0 && <div className="flex min-h-48 flex-col items-center justify-center text-center"><ShieldCheck className="h-5 w-5 text-muted-foreground" /><p className="mt-3 font-medium">尚未设置岗位分工</p><p className="mt-1 text-sm text-muted-foreground">现有超级管理员按平台所有者权限运行。</p></div>}
        {data.map((item) => (
          <button key={item.user_id} className="grid w-full gap-3 py-4 text-left sm:grid-cols-[1fr_180px_100px] sm:items-center" onClick={() => { setForm({ user_id: item.user_id, admin_role: item.admin_role, active: item.active }); setOpen(true); }}>
            <div><p className="font-medium">{item.user?.full_name || item.user?.email || item.user_id}</p><p className="mt-1 text-xs text-muted-foreground">{item.user?.email || item.user_id}</p></div>
            <Badge variant="outline" className="w-fit">{ROLE_NAMES[item.admin_role] ?? item.admin_role}</Badge>
            <span className={`text-sm ${item.active ? 'text-success' : 'text-muted-foreground'}`}>{item.active ? '已启用' : '已停用'}</span>
          </button>
        ))}
      </div>
      <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>设置平台管理员职责</DialogTitle></DialogHeader><div className="space-y-4"><div className="grid gap-2"><Label htmlFor="platform-admin-user">用户 ID</Label><Input id="platform-admin-user" value={form.user_id} onChange={(event) => setForm({ ...form, user_id: event.target.value })} disabled={data.some((item) => item.user_id === form.user_id)} /></div><div className="grid gap-2"><Label>岗位</Label><Select value={form.admin_role} onValueChange={(value) => setForm({ ...form, admin_role: value })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(ROLE_NAMES).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div><div className="flex items-center justify-between border-y py-3"><div><p className="text-sm font-medium">允许进入平台后台</p><p className="text-xs text-muted-foreground">停用后保留职责记录，但拒绝后台操作。</p></div><Switch checked={form.active} onCheckedChange={(active) => setForm({ ...form, active })} /></div></div><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>取消</Button><Button onClick={save} disabled={mutation.isPending}>保存</Button></DialogFooter></DialogContent></Dialog>
    </section>
  );
}
