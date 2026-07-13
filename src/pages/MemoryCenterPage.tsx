import { useMemo, useState } from 'react';
import {
  Archive,
  Brain,
  Building2,
  Check,
  Clock3,
  Lock,
  Pencil,
  Plus,
  RotateCcw,
  Trash2,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  type CreateMemoryInput,
  type MemoryRecord,
  type MemoryState,
  type MemoryVisibility,
  useCreateMemory,
  useDeleteMemory,
  useMemories,
  useUpdateMemory,
} from '@/hooks/useMemories';
import { cn } from '@/lib/utils';

const CATEGORY_LABELS: Record<string, string> = {
  preference: '个人偏好',
  explicit_memory: '明确记忆',
  fact: '业务事实',
  episodic: '经历记录',
  instrument_identity: '仪器身份',
  calibration_baseline: '校准基线',
  maintenance_episode: '维修事件',
  experiment_method: '实验方法',
  compliance_evidence: '合规证据',
};

const STATE_LABELS: Record<MemoryState, string> = {
  proposed: '待确认',
  pending_review: '待确认',
  confirmed: '已确认',
  active: '使用中',
  expired: '已过期',
  rejected: '已拒绝',
  archived: '已归档',
};

const EMPTY_FORM: CreateMemoryInput = {
  key: '',
  value: '',
  category: 'explicit_memory',
  visibility: 'private',
  importance: 0.7,
  confidence: 1,
  evidence_ref: '',
};

function VisibilityIcon({ value }: { value: MemoryVisibility }) {
  const Icon = value === 'private' ? Lock : value === 'team' ? Users : Building2;
  return <Icon className="h-3.5 w-3.5" />;
}

export default function MemoryCenterPage() {
  const memories = useMemories();
  const createMemory = useCreateMemory();
  const updateMemory = useUpdateMemory();
  const deleteMemory = useDeleteMemory();
  const [filter, setFilter] = useState<'current' | 'review' | 'archived'>('current');
  const [editing, setEditing] = useState<MemoryRecord | null>(null);
  const [deleting, setDeleting] = useState<MemoryRecord | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<CreateMemoryInput>(EMPTY_FORM);

  const rows = useMemo(() => {
    const all = memories.data ?? [];
    if (filter === 'review') return all.filter((item) => ['proposed', 'pending_review'].includes(item.lifecycle_state));
    if (filter === 'archived') return all.filter((item) => ['archived', 'expired', 'rejected'].includes(item.lifecycle_state));
    return all.filter((item) => ['active', 'confirmed'].includes(item.lifecycle_state));
  }, [filter, memories.data]);

  const reviewCount = (memories.data ?? []).filter((item) => ['proposed', 'pending_review'].includes(item.lifecycle_state)).length;
  const sharedCount = (memories.data ?? []).filter((item) => item.visibility !== 'private').length;

  const changeState = async (memory: MemoryRecord, state: MemoryState) => {
    await updateMemory.mutateAsync({ id: memory.id, lifecycle_state: state });
    toast.success(state === 'confirmed' ? '记忆已确认' : state === 'archived' ? '记忆已归档' : '记忆已恢复');
  };

  const submitCreate = async () => {
    if (!form.key.trim() || !form.value.trim()) return;
    await createMemory.mutateAsync(form);
    setCreateOpen(false);
    setForm(EMPTY_FORM);
    toast.success('记忆已保存');
  };

  const submitEdit = async () => {
    if (!editing) return;
    await updateMemory.mutateAsync({
      id: editing.id,
      value: editing.value,
      visibility: editing.visibility,
      expires_at: editing.expires_at,
    });
    setEditing(null);
    toast.success('记忆已更新');
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-8 lg:px-8">
      <header className="flex flex-col gap-5 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Brain className="h-4 w-4" />
            个人 AI 设置
          </div>
          <h1 className="text-2xl font-semibold tracking-normal">AI 记忆</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            查看助手记住的事实、偏好和仪器工作记录。未经确认的内容不会参与回答。
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />新增记忆
        </Button>
      </header>

      <section className="grid grid-cols-3 border-b py-5">
        <div><p className="text-2xl font-semibold">{(memories.data ?? []).filter((item) => ['active', 'confirmed'].includes(item.lifecycle_state)).length}</p><p className="mt-1 text-xs text-muted-foreground">使用中</p></div>
        <div className="border-l pl-5"><p className="text-2xl font-semibold">{reviewCount}</p><p className="mt-1 text-xs text-muted-foreground">待确认</p></div>
        <div className="border-l pl-5"><p className="text-2xl font-semibold">{sharedCount}</p><p className="mt-1 text-xs text-muted-foreground">已共享</p></div>
      </section>

      <div className="flex gap-1 border-b py-4" role="tablist" aria-label="记忆筛选">
        {([['current', '当前'], ['review', `待确认 ${reviewCount || ''}`], ['archived', '归档']] as const).map(([value, label]) => (
          <Button key={value} size="sm" variant={filter === value ? 'secondary' : 'ghost'} onClick={() => setFilter(value)}>{label}</Button>
        ))}
      </div>

      <div className="divide-y">
        {memories.isLoading && <p className="py-12 text-center text-sm text-muted-foreground">正在读取记忆...</p>}
        {!memories.isLoading && rows.length === 0 && (
          <div className="py-16 text-center"><Brain className="mx-auto h-8 w-8 text-muted-foreground/50" /><p className="mt-4 text-sm font-medium">这里还没有记忆</p><p className="mt-1 text-sm text-muted-foreground">助手只会保存有长期价值的信息。</p></div>
        )}
        {rows.map((memory) => (
          <article key={memory.id} className="group grid gap-3 py-5 md:grid-cols-[150px_1fr_auto] md:items-start">
            <div>
              <p className="text-xs font-medium text-muted-foreground">{CATEGORY_LABELS[memory.category] ?? memory.category}</p>
              <span className={cn('mt-2 inline-flex items-center rounded px-2 py-0.5 text-xs', ['pending_review', 'proposed'].includes(memory.lifecycle_state) ? 'bg-amber-50 text-amber-800' : 'bg-muted text-muted-foreground')}>{STATE_LABELS[memory.lifecycle_state]}</span>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2"><h2 className="truncate text-sm font-semibold">{memory.key}</h2><span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><VisibilityIcon value={memory.visibility} />{memory.visibility === 'private' ? '仅自己' : memory.visibility === 'team' ? '团队' : '组织'}</span></div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-foreground/80">{memory.value}</p>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>来源：{memory.provenance?.source || '系统提取'}</span>
                {memory.confidence != null && <span>置信度 {Math.round(memory.confidence * 100)}%</span>}
                {memory.evidence_ref && <span className="max-w-xs truncate">证据：{memory.evidence_ref}</span>}
                {memory.expires_at && <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{new Date(memory.expires_at).toLocaleDateString()}</span>}
              </div>
            </div>
            <div className="flex items-center gap-1 md:opacity-0 md:transition-opacity md:group-hover:opacity-100 md:group-focus-within:opacity-100">
              {['pending_review', 'proposed'].includes(memory.lifecycle_state) && <IconAction label="确认" icon={Check} onClick={() => changeState(memory, 'confirmed')} />}
              {['archived', 'expired', 'rejected'].includes(memory.lifecycle_state) ? <IconAction label="恢复" icon={RotateCcw} onClick={() => changeState(memory, 'confirmed')} /> : <IconAction label="归档" icon={Archive} onClick={() => changeState(memory, 'archived')} />}
              <IconAction label="编辑" icon={Pencil} onClick={() => setEditing({ ...memory })} />
              <IconAction label="彻底忘记" icon={Trash2} destructive onClick={() => setDeleting(memory)} />
            </div>
          </article>
        ))}
      </div>

      <MemoryDialog open={createOpen} title="新增记忆" form={form} onOpenChange={setCreateOpen} onChange={setForm} onSubmit={submitCreate} loading={createMemory.isPending} />
      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>编辑记忆</DialogTitle></DialogHeader>
          {editing && <div className="space-y-4"><div className="space-y-2"><Label>内容</Label><Textarea rows={6} value={editing.value} onChange={(event) => setEditing({ ...editing, value: event.target.value })} /></div><div className="space-y-2"><Label>可见范围</Label><VisibilitySelect value={editing.visibility} onChange={(value) => setEditing({ ...editing, visibility: value })} /></div></div>}
          <DialogFooter><Button variant="outline" onClick={() => setEditing(null)}>取消</Button><Button onClick={submitEdit} disabled={updateMemory.isPending}>保存</Button></DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>彻底忘记这条记忆？</DialogTitle></DialogHeader>
          <p className="text-sm leading-6 text-muted-foreground">删除后，助手不会再使用“{deleting?.key}”，此操作不可撤销。</p>
          <DialogFooter><Button variant="outline" onClick={() => setDeleting(null)}>取消</Button><Button variant="destructive" disabled={deleteMemory.isPending} onClick={async () => { if (!deleting) return; await deleteMemory.mutateAsync(deleting.id); setDeleting(null); toast.success('记忆已删除'); }}>确认忘记</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function IconAction({ label, icon: Icon, onClick, destructive = false }: { label: string; icon: typeof Check; onClick: () => void; destructive?: boolean }) {
  return <Tooltip><TooltipTrigger asChild><Button size="icon" variant="ghost" className={cn('h-8 w-8', destructive && 'text-destructive hover:text-destructive')} onClick={onClick} aria-label={label}><Icon className="h-4 w-4" /></Button></TooltipTrigger><TooltipContent>{label}</TooltipContent></Tooltip>;
}

function VisibilitySelect({ value, onChange }: { value: MemoryVisibility; onChange: (value: MemoryVisibility) => void }) {
  return <Select value={value} onValueChange={(next) => onChange(next as MemoryVisibility)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="private">仅自己</SelectItem><SelectItem value="team">团队</SelectItem><SelectItem value="organization">组织管理员</SelectItem></SelectContent></Select>;
}

function MemoryDialog({ open, title, form, onOpenChange, onChange, onSubmit, loading }: { open: boolean; title: string; form: CreateMemoryInput; onOpenChange: (open: boolean) => void; onChange: (form: CreateMemoryInput) => void; onSubmit: () => void; loading: boolean }) {
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader><div className="space-y-4"><div className="space-y-2"><Label>名称</Label><Input value={form.key} onChange={(event) => onChange({ ...form, key: event.target.value })} placeholder="例如：质谱仪 MS-01 校准基线" /></div><div className="space-y-2"><Label>类型</Label><Select value={form.category} onValueChange={(category) => onChange({ ...form, category })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label>内容</Label><Textarea rows={6} value={form.value} onChange={(event) => onChange({ ...form, value: event.target.value })} placeholder="只记录未来对话真正需要的信息" /></div>{['calibration_baseline', 'compliance_evidence'].includes(form.category) && <div className="space-y-2"><Label>证据引用</Label><Input value={form.evidence_ref} onChange={(event) => onChange({ ...form, evidence_ref: event.target.value })} placeholder="校准证书、SOP 或原始记录编号" /></div>}<div className="space-y-2"><Label>可见范围</Label><VisibilitySelect value={form.visibility} onChange={(visibility) => onChange({ ...form, visibility })} /></div></div><DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button><Button onClick={onSubmit} disabled={loading || !form.key.trim() || !form.value.trim()}>保存记忆</Button></DialogFooter></DialogContent></Dialog>;
}
