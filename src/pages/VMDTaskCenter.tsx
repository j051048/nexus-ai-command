/**
 * VMD 任务中心
 * 创建任务、筛选、任务列表、任务详情（WBS树 + 审核 + 日志）
 */

import React, { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import {
  Plus,
  Search,
  ListTodo,
  Bot,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  FileDown,
  ChevronRight,
  Play,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Filter,
  CalendarDays,
} from 'lucide-react';
import {
  useVMDTasks,
  useVMDTaskDetail,
  useCreateVMDTask,
  useAuditSubTask,
  type VMDTask,
  type VMDSubTask,
} from '@/hooks/useVMD';
import { SCENES } from '@/components/vmd/SceneSelector';
import { toast } from 'sonner';

// 状态配置
const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  pending: { label: '待处理', color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300', icon: Clock },
  planning: { label: '规划中', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300', icon: ListTodo },
  executing: { label: '执行中', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300', icon: Play },
  reviewing: { label: '审核中', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300', icon: Eye },
  done: { label: '已完成', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300', icon: CheckCircle2 },
  failed: { label: '失败', color: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300', icon: XCircle },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: '低', color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
  normal: { label: '普通', color: 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400' },
  high: { label: '高', color: 'bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-400' },
  urgent: { label: '紧急', color: 'bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-400' },
};

const AGENT_ICONS: Record<string, string> = {
  director: '\uD83C\uDFAF',
  content: '\u270D\uFE0F',
  design: '\uD83C\uDFA8',
  media: '\uD83D\uDCE2',
  clue: '\uD83D\uDD0D',
  compliance: '\uD83D\uDEE1\uFE0F',
  operation: '\u2699\uFE0F',
  synergy: '\uD83D\uDD17',
  pr: '\uD83D\uDCF0',
  sales: '\uD83D\uDCB0',
};

const SCENE_NAMES: Record<string, string> = Object.fromEntries(SCENES.map(s => [s.code, s.name]));

export default function VMDTaskCenter() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(searchParams.get('new') === '1');
  const [detailId, setDetailId] = useState<string | null>(searchParams.get('detail'));

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [sceneFilter, setSceneFilter] = useState<string>(searchParams.get('scene') || '');
  const [searchText, setSearchText] = useState('');

  // Form state
  const [formTitle, setFormTitle] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formScene, setFormScene] = useState(searchParams.get('scene') || '');
  const [formPriority, setFormPriority] = useState('normal');
  const [formDeadline, setFormDeadline] = useState('');

  // Queries
  const { data: tasks, isLoading } = useVMDTasks({
    status: statusFilter || undefined,
    priority: priorityFilter || undefined,
    scene_code: sceneFilter || undefined,
  });
  const { data: taskDetail, isLoading: detailLoading } = useVMDTaskDetail(detailId);
  const createTask = useCreateVMDTask();
  const auditSubTask = useAuditSubTask();

  // Filtered tasks
  const filteredTasks = useMemo(() => {
    if (!tasks) return [];
    if (!searchText) return tasks;
    const lower = searchText.toLowerCase();
    return tasks.filter(t =>
      t.title.toLowerCase().includes(lower) ||
      t.task_code.toLowerCase().includes(lower)
    );
  }, [tasks, searchText]);

  const handleCreate = async () => {
    if (!formTitle.trim() || !formScene) {
      toast.error('请填写任务标题和选择场景');
      return;
    }
    await createTask.mutateAsync({
      title: formTitle,
      description: formDesc,
      scene_code: formScene,
      priority: formPriority,
      deadline: formDeadline || undefined,
    });
    setCreateOpen(false);
    setFormTitle('');
    setFormDesc('');
    setFormScene('');
    setFormPriority('normal');
    setFormDeadline('');
  };

  const handleAudit = async (subTaskId: string, action: 'approve' | 'reject') => {
    await auditSubTask.mutateAsync({ subTaskId, action });
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">任务中心</h1>
          <p className="text-muted-foreground">管理和追踪所有营销任务的执行进度</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          创建新任务
        </Button>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索任务名称或编号..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">全部状态</SelectItem>
                {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="全部优先级" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">全部优先级</SelectItem>
                {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sceneFilter} onValueChange={setSceneFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="全部场景" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">全部场景</SelectItem>
                {SCENES.map(s => (
                  <SelectItem key={s.code} value={s.code}>{s.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Task List */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="text-center py-20 bg-muted/10 rounded-xl border border-dashed">
          <ListTodo className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium">暂无任务</h3>
          <p className="text-muted-foreground mb-6">创建您的第一个营销任务，AI Agent 将自动规划和执行</p>
          <Button variant="outline" onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            创建任务
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTasks.map((task) => {
            const statusCfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
            const priorityCfg = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.normal;
            const StatusIcon = statusCfg.icon;
            return (
              <Card
                key={task.id}
                className="hover:shadow-md transition-all cursor-pointer border-border/50 hover:border-primary/50"
                onClick={() => setDetailId(task.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                      <StatusIcon className={cn("w-5 h-5", statusCfg.color.includes('text-') ? statusCfg.color.split(' ').find(c => c.startsWith('text-')) : 'text-muted-foreground')} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-muted-foreground font-mono">{task.task_code}</span>
                        <Badge className={cn("text-[10px]", statusCfg.color)}>{statusCfg.label}</Badge>
                        <Badge className={cn("text-[10px]", priorityCfg.color)}>{priorityCfg.label}</Badge>
                      </div>
                      <p className="text-sm font-medium truncate">{task.title}</p>
                    </div>
                    <div className="hidden sm:flex items-center gap-3 shrink-0">
                      <Badge variant="outline" className="text-xs">
                        {SCENE_NAMES[task.scene_code] || task.scene_code}
                      </Badge>
                      <div className="w-24">
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
                          <span>进度</span>
                          <span>{task.progress}%</span>
                        </div>
                        <Progress value={task.progress} className="h-1.5" />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(task.created_at).toLocaleDateString('zh-CN')}
                      </span>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Task Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>创建新任务</DialogTitle>
            <DialogDescription>描述您的营销需求，AI Agent 将自动规划执行方案</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="task-title">任务标题</Label>
              <Input
                id="task-title"
                placeholder="例如：Q2新品上市全案策划"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-desc">任务描述</Label>
              <Textarea
                id="task-desc"
                placeholder="用自然语言描述您的需求，AI 将自动拆解为可执行子任务..."
                rows={4}
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>场景类型</Label>
                <Select value={formScene} onValueChange={setFormScene}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择场景" />
                  </SelectTrigger>
                  <SelectContent>
                    {SCENES.map(s => (
                      <SelectItem key={s.code} value={s.code}>
                        {s.icon} {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>优先级</Label>
                <Select value={formPriority} onValueChange={setFormPriority}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-deadline">截止日期（可选）</Label>
              <Input
                id="task-deadline"
                type="date"
                value={formDeadline}
                onChange={(e) => setFormDeadline(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={createTask.isPending}>
              {createTask.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              创建任务
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Task Detail Sheet */}
      <Sheet open={!!detailId} onOpenChange={(open) => { if (!open) setDetailId(null); }}>
        <SheetContent className="w-full sm:max-w-xl overflow-hidden flex flex-col">
          <SheetHeader>
            <SheetTitle>{taskDetail?.title || '任务详情'}</SheetTitle>
            <SheetDescription>
              {taskDetail?.task_code} | {SCENE_NAMES[taskDetail?.scene_code || ''] || taskDetail?.scene_code}
            </SheetDescription>
          </SheetHeader>
          <ScrollArea className="flex-1 mt-4 -mx-6 px-6">
            {detailLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : taskDetail ? (
              <div className="space-y-6 pb-6">
                {/* Task Overview */}
                <div className="flex items-center gap-3 flex-wrap">
                  <Badge className={cn(STATUS_CONFIG[taskDetail.status]?.color)}>
                    {STATUS_CONFIG[taskDetail.status]?.label}
                  </Badge>
                  <Badge className={cn(PRIORITY_CONFIG[taskDetail.priority]?.color)}>
                    {PRIORITY_CONFIG[taskDetail.priority]?.label}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    创建于 {new Date(taskDetail.created_at).toLocaleString('zh-CN')}
                  </span>
                </div>

                {taskDetail.description && (
                  <div>
                    <h4 className="text-sm font-medium mb-1">任务描述</h4>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">{taskDetail.description}</p>
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">总体进度</span>
                    <span className="text-sm text-muted-foreground">{taskDetail.progress}%</span>
                  </div>
                  <Progress value={taskDetail.progress} className="h-2" />
                </div>

                <Separator />

                {/* WBS Sub-tasks */}
                <div>
                  <h4 className="text-sm font-medium mb-3">子任务 (WBS)</h4>
                  {taskDetail.sub_tasks && taskDetail.sub_tasks.length > 0 ? (
                    <div className="space-y-3">
                      {taskDetail.sub_tasks.map((sub, idx) => {
                        const subStatus = STATUS_CONFIG[sub.status] || STATUS_CONFIG.pending;
                        return (
                          <Card key={sub.id} className="border-border/50">
                            <CardContent className="p-3">
                              <div className="flex items-start gap-3">
                                <span className="text-lg shrink-0 mt-0.5">
                                  {AGENT_ICONS[sub.agent_role] || '\uD83E\uDD16'}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs text-muted-foreground">#{idx + 1}</span>
                                    <Badge className={cn("text-[10px]", subStatus.color)}>{subStatus.label}</Badge>
                                  </div>
                                  <p className="text-sm font-medium">{sub.title}</p>
                                  {sub.output && (
                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{sub.output}</p>
                                  )}
                                  {sub.status === 'reviewing' && (
                                    <div className="flex gap-2 mt-2">
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 text-xs text-green-600 hover:bg-green-50"
                                        onClick={() => handleAudit(sub.id, 'approve')}
                                        disabled={auditSubTask.isPending}
                                      >
                                        <ThumbsUp className="w-3 h-3 mr-1" /> 通过
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 text-xs text-red-600 hover:bg-red-50"
                                        onClick={() => handleAudit(sub.id, 'reject')}
                                        disabled={auditSubTask.isPending}
                                      >
                                        <ThumbsDown className="w-3 h-3 mr-1" /> 驳回
                                      </Button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">AI 正在规划子任务...</p>
                  )}
                </div>

                <Separator />

                {/* Actions */}
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">
                    <FileDown className="w-4 h-4 mr-1" /> 导出结果
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8">未找到任务详情</p>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  );
}
