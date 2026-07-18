import { useMemo, useState, type ReactNode } from "react";
import { CalendarClock, History, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  type AccessChange,
  useAccessChangeAction,
  useAdminOrganization360,
  useUpsertCommercialRecord,
} from "@/hooks/useSuperAdminConsole";

type Organization360Data = NonNullable<ReturnType<typeof useAdminOrganization360>["data"]>;

export function AccessHistory({ changes, canRollback }: { changes: AccessChange[]; canRollback: boolean }) {
  const [action, setAction] = useState<{ item: AccessChange; type: "cancel" | "rollback" } | null>(null);
  const [reason, setReason] = useState("");
  const mutation = useAccessChangeAction();

  const submit = async () => {
    if (!action || reason.trim().length < 2) return toast.error("请填写操作原因");
    try {
      await mutation.mutateAsync({ changeId: action.item.id, action: action.type, reason: reason.trim() });
      toast.success(action.type === "rollback" ? "会员状态已回滚" : "预约变更已取消");
      setAction(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    }
  };

  return (
    <section>
      <h3 className="text-sm font-medium">权益版本</h3>
      <div className="mt-3 divide-y border-y">
        {changes.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">暂无权益变更记录</p>}
        {changes.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div>
              <p className="text-sm font-medium">
                {ORGANIZATION_PLAN_NAMES[item.next_snapshot.plan] ?? item.next_snapshot.plan} · {item.change_status}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{item.reason} · {new Date(item.effective_at).toLocaleString("zh-CN")}</p>
            </div>
            {canRollback && item.change_status === "scheduled" && (
              <Button size="sm" variant="ghost" onClick={() => { setReason(""); setAction({ item, type: "cancel" }); }}>
                取消预约
              </Button>
            )}
            {canRollback && item.change_status === "applied" && (
              <Button size="sm" variant="ghost" onClick={() => { setReason(""); setAction({ item, type: "rollback" }); }}>
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
            <DialogTitle>{action?.type === "rollback" ? "回滚会员状态" : "取消预约变更"}</DialogTitle>
          </DialogHeader>
          <Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="说明本次操作原因" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAction(null)}>取消</Button>
            <Button onClick={submit} disabled={mutation.isPending}>确认</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export function CommercialRecords({ data, canEdit }: { data: Organization360Data; canEdit: boolean }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    order_number: "",
    contract_number: "",
    amount: "",
    payment_status: "pending",
    due_at: "",
    notes: "",
  });
  const mutation = useUpsertCommercialRecord();

  const save = async () => {
    if (!form.order_number.trim()) return toast.error("请填写订单编号");
    try {
      await mutation.mutateAsync({
        org_id: data.id,
        order_number: form.order_number.trim(),
        contract_number: form.contract_number || null,
        amount_cents: Math.round(Number(form.amount || 0) * 100),
        payment_status: form.payment_status,
        due_at: form.due_at ? new Date(`${form.due_at}T23:59:59`).toISOString() : null,
        invoice_status: "none",
        discount_cents: 0,
        currency: "CNY",
        gifted_days: 0,
        notes: form.notes || null,
      });
      toast.success("商业记录已保存");
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    }
  };

  return (
    <section>
      <div className="flex items-end justify-between">
        <div>
          <h3 className="text-sm font-medium">合同、回款与发票</h3>
          <p className="mt-1 text-sm text-muted-foreground">商业凭证与会员权益分开记录。</p>
        </div>
        {canEdit && <Button size="sm" onClick={() => setOpen(true)}>新增记录</Button>}
      </div>
      <div className="mt-4 divide-y border-y">
        {data.commercial_records.length === 0 && <p className="py-10 text-center text-sm text-muted-foreground">暂无商业记录</p>}
        {data.commercial_records.map((item) => (
          <div key={item.id} className="grid gap-2 py-4 sm:grid-cols-[1fr_150px_120px] sm:items-center">
            <div>
              <p className="font-medium">{item.order_number}</p>
              <p className="text-xs text-muted-foreground">合同 {item.contract_number || "未关联"} · 发票 {item.invoice_status}</p>
            </div>
            <p className="font-medium tabular-nums">¥{((item.amount_cents - item.discount_cents) / 100).toLocaleString()}</p>
            <Badge variant="outline" className="w-fit">{item.payment_status}</Badge>
          </div>
        ))}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>新增商业记录</DialogTitle></DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="订单编号"><Input value={form.order_number} onChange={(event) => setForm({ ...form, order_number: event.target.value })} /></Field>
            <Field label="合同编号"><Input value={form.contract_number} onChange={(event) => setForm({ ...form, contract_number: event.target.value })} /></Field>
            <Field label="实收前金额（元）"><Input type="number" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></Field>
            <Field label="回款状态">
              <Select value={form.payment_status} onValueChange={(value) => setForm({ ...form, payment_status: value })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["pending", "partial", "paid", "overdue", "waived"].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
            <Field label="应收日期"><Input type="date" value={form.due_at} onChange={(event) => setForm({ ...form, due_at: event.target.value })} /></Field>
            <Field label="备注"><Input value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
            <Button onClick={save} disabled={mutation.isPending}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export function UserList({ data }: { data: Organization360Data }) {
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
            <Badge variant="outline" className="w-fit">{user.role}</Badge>
            <p className="text-xs text-muted-foreground">
              {user.last_active_at ? `最近活跃 ${new Date(user.last_active_at).toLocaleString("zh-CN")}` : "暂无活跃记录"}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function Timeline({ data }: { data: Organization360Data }) {
  const timeline = useMemo(
    () => [
      ...data.audit_timeline.map((item) => ({ id: item.id, title: item.action, detail: String(item.details?.reason ?? ""), at: item.created_at, icon: History })),
      ...data.access_requests.map((item) => ({ id: item.id, title: `会员申请 · ${item.status}`, detail: item.note ?? "", at: item.created_at, icon: CalendarClock })),
    ].sort((a, b) => b.at.localeCompare(a.at)),
    [data.access_requests, data.audit_timeline],
  );

  return (
    <section>
      <h3 className="text-sm font-medium">操作时间线</h3>
      <div className="mt-4 space-y-0">
        {timeline.map((item) => (
          <div key={`${item.title}:${item.id}`} className="grid grid-cols-[28px_1fr] gap-3 border-l pb-5 pl-4">
            <item.icon className="-ml-[30px] h-4 w-4 bg-background text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{item.title}</p>
              {item.detail && <p className="mt-1 text-sm text-muted-foreground">{item.detail}</p>}
              <p className="mt-1 text-xs text-muted-foreground">{new Date(item.at).toLocaleString("zh-CN")}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
