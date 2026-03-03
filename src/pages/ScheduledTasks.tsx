import React, { useState } from 'react';
import {
  useScheduledTasks,
  useCreateScheduledTask,
  useUpdateScheduledTask,
  useDeleteScheduledTask,
  useRunScheduledTask,
  ScheduledTask,
  CreateScheduledTaskInput,
} from '@/hooks/useScheduledTasks';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Plus,
  Play,
  Trash2,
  Pencil,
  Clock,
  Loader2,
  Calendar,
} from 'lucide-react';
import { toast } from 'sonner';

const DAY_NAMES: Record<number, string> = {
  0: '周一', 1: '周二', 2: '周三', 3: '周四',
  4: '周五', 5: '周六', 6: '周日',
};

function formatSchedule(task: ScheduledTask): string {
  const time = task.hour != null ? `${String(task.hour).padStart(2, '0')}:${String(task.minute).padStart(2, '0')}` : '';
  switch (task.schedule_type) {
    case 'daily':
      return `每天 ${time}`;
    case 'weekly':
      return `每${DAY_NAMES[task.day_of_week ?? 0] ?? '?'} ${time}`;
    case 'once':
      return `一次性 ${time}`;
    case 'interval':
      return `每 ${task.interval_minutes} 分钟`;
    default:
      return task.schedule_type;
  }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso.slice(0, 16);
  }
}

const defaultForm: CreateScheduledTaskInput = {
  name: '',
  prompt: '',
  schedule_type: 'daily',
  hour: 9,
  minute: 0,
  day_of_week: null,
  interval_minutes: null,
  notify_method: 'notification',
};

export default function ScheduledTasks() {
  const [showInactive, setShowInactive] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CreateScheduledTaskInput>({ ...defaultForm });
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const { data: tasks = [], isLoading } = useScheduledTasks(showInactive);
  const createTask = useCreateScheduledTask();
  const updateTask = useUpdateScheduledTask();
  const deleteTask = useDeleteScheduledTask();
  const runTask = useRunScheduledTask();

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...defaultForm });
    setDialogOpen(true);
  };

  const openEdit = (task: ScheduledTask) => {
    setEditingId(task.id);
    setForm({
      name: task.name,
      prompt: task.prompt,
      schedule_type: task.schedule_type,
      hour: task.hour,
      minute: task.minute,
      day_of_week: task.day_of_week,
      interval_minutes: task.interval_minutes,
      notify_method: task.notify_method || 'notification',
    });
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.name.trim() || !form.prompt.trim()) {
      toast.error('请填写任务名称和 AI 提示词');
      return;
    }

    try {
      if (editingId) {
        await updateTask.mutateAsync({ id: editingId, ...form });
        toast.success('定时任务已更新');
      } else {
        await createTask.mutateAsync(form);
        toast.success('定时任务创建成功');
      }
      setDialogOpen(false);
    } catch (e: any) {
      toast.error(e.message || '操作失败');
    }
  };

  const handleToggleActive = async (task: ScheduledTask) => {
    try {
      await updateTask.mutateAsync({ id: task.id, is_active: !task.is_active });
      toast.success(task.is_active ? '已停用' : '已启用');
    } catch (e: any) {
      toast.error(e.message || '操作失败');
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirmId) return;
    try {
      await deleteTask.mutateAsync(deleteConfirmId);
      toast.success('已删除');
      setDeleteConfirmId(null);
    } catch (e: any) {
      toast.error(e.message || '删除失败');
    }
  };

  const handleRun = async (id: string) => {
    try {
      await runTask.mutateAsync(id);
      toast.success('任务已触发执行，结果将通过通知推送');
    } catch (e: any) {
      toast.error(e.message || '触发失败');
    }
  };

  const isSaving = createTask.isPending || updateTask.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Clock className="w-6 h-6 text-primary" />
            定时任务管理
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            管理 AI 自动执行的定时任务和提醒
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Switch checked={showInactive} onCheckedChange={setShowInactive} />
            显示已停用
          </label>
          <Button onClick={openCreate} className="gap-2">
            <Plus className="w-4 h-4" />
            新建任务
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="border border-border rounded-lg bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>执行计划</TableHead>
              <TableHead>下次执行</TableHead>
              <TableHead className="text-center">已执行</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : tasks.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                  <Calendar className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p>暂无定时任务</p>
                  <p className="text-xs mt-1">点击「新建任务」或通过 AI 对话创建（例如"每天9点提醒我检查客户回复"）</p>
                </TableCell>
              </TableRow>
            ) : (
              tasks.map((task) => (
                <TableRow key={task.id}>
                  <TableCell>
                    <div>
                      <p className="font-medium text-foreground">{task.name}</p>
                      <p className="text-xs text-muted-foreground line-clamp-1 max-w-[200px]">{task.prompt}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{formatSchedule(task)}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDateTime(task.next_execution_at)}
                  </TableCell>
                  <TableCell className="text-center text-sm">
                    {task.execution_count}
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={task.is_active}
                      onCheckedChange={() => handleToggleActive(task)}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleRun(task.id)}
                        disabled={runTask.isPending}
                        title="手动执行一次"
                      >
                        <Play className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => openEdit(task)}
                        title="编辑"
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => setDeleteConfirmId(task.id)}
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{editingId ? '编辑定时任务' : '新建定时任务'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>任务名称</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="例如：检查客户回复"
              />
            </div>
            <div className="space-y-2">
              <Label>AI 提示词</Label>
              <Textarea
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                placeholder="描述 AI 需要执行什么任务..."
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>调度类型</Label>
                <Select
                  value={form.schedule_type}
                  onValueChange={(v) => setForm({ ...form, schedule_type: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">每天</SelectItem>
                    <SelectItem value="weekly">每周</SelectItem>
                    <SelectItem value="once">一次性</SelectItem>
                    <SelectItem value="interval">固定间隔</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {form.schedule_type === 'weekly' && (
                <div className="space-y-2">
                  <Label>星期几</Label>
                  <Select
                    value={String(form.day_of_week ?? 0)}
                    onValueChange={(v) => setForm({ ...form, day_of_week: Number(v) })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(DAY_NAMES).map(([k, v]) => (
                        <SelectItem key={k} value={k}>{v}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            {form.schedule_type === 'interval' ? (
              <div className="space-y-2">
                <Label>间隔（分钟）</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.interval_minutes ?? ''}
                  onChange={(e) => setForm({ ...form, interval_minutes: Number(e.target.value) || null })}
                  placeholder="例如：60"
                />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>小时 (0-23)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={form.hour ?? ''}
                    onChange={(e) => setForm({ ...form, hour: Number(e.target.value) })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>分钟 (0-59)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={59}
                    value={form.minute ?? 0}
                    onChange={(e) => setForm({ ...form, minute: Number(e.target.value) })}
                  />
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {editingId ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={!!deleteConfirmId} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">删除后不可恢复，确定要删除此定时任务吗？</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>取消</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteTask.isPending}>
              {deleteTask.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
