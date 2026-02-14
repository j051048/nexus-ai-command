import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Plus,
  Workflow,
  MoreVertical,
  Pencil,
  Trash2,
  Power,
  PowerOff,
  Star,
  Loader2,
  FileX2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  useWorkflows,
  useDeleteWorkflow,
  useToggleWorkflow,
  useSetDefaultWorkflow,
} from '@/hooks/useWorkflows';
import type { Workflow as WorkflowType } from '@/hooks/useWorkflows';

// 审批类型标签
const APPROVAL_TYPE_LABELS: Record<string, string> = {
  expense: '费用报销',
  purchase: '采购申请',
  leave: '请假审批',
  travel: '出差申请',
  contract: '合同审批',
  general: '通用审批',
};

export function WorkflowList() {
  const navigate = useNavigate();
  const { data: workflows = [], isLoading, error } = useWorkflows();
  const deleteMutation = useDeleteWorkflow();
  const toggleMutation = useToggleWorkflow();
  const setDefaultMutation = useSetDefaultWorkflow();

  const [deleteDialogId, setDeleteDialogId] = useState<string | null>(null);

  // 删除流程
  const handleDelete = async () => {
    if (!deleteDialogId) return;
    try {
      await deleteMutation.mutateAsync(deleteDialogId);
      toast.success('流程已删除');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '删除失败');
    } finally {
      setDeleteDialogId(null);
    }
  };

  // 启用/禁用流程
  const handleToggle = async (workflow: WorkflowType) => {
    try {
      await toggleMutation.mutateAsync(workflow.id);
      toast.success(workflow.is_active ? '流程已禁用' : '流程已启用');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '操作失败');
    }
  };

  // 设为默认
  const handleSetDefault = async (workflow: WorkflowType) => {
    try {
      await setDefaultMutation.mutateAsync(workflow.id);
      toast.success(`已将「${workflow.name}」设为默认流程`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '设置失败');
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="w-6 h-6" />
            流程设计器
          </h1>
          <p className="text-muted-foreground mt-1">
            可视化设计和管理审批流程
          </p>
        </div>
        <Button onClick={() => navigate('/workflows/new')} className="gap-2">
          <Plus className="w-4 h-4" />
          新建流程
        </Button>
      </div>

      {/* 加载状态 */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-destructive">
              加载失败: {error instanceof Error ? error.message : '未知错误'}
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              重新加载
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 空状态 */}
      {!isLoading && !error && workflows.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <FileX2 className="w-16 h-16 text-muted-foreground/40 mb-4" />
            <h3 className="text-lg font-medium mb-2">暂无流程</h3>
            <p className="text-sm text-muted-foreground mb-6">
              点击「新建流程」开始设计您的第一个审批流程
            </p>
            <Button onClick={() => navigate('/workflows/new')} className="gap-2">
              <Plus className="w-4 h-4" />
              新建流程
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 流程列表 */}
      {!isLoading && workflows.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {workflows.map((wf) => (
            <Card
              key={wf.id}
              className={`
                group relative cursor-pointer transition-all hover:shadow-md
                ${wf.is_default ? 'ring-2 ring-primary/50' : ''}
              `}
              onClick={() => navigate(`/workflows/${wf.id}`)}
            >
              <CardContent className="pt-5 pb-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold truncate">{wf.name}</h3>
                      {wf.is_default && (
                        <Star className="w-4 h-4 text-yellow-500 flex-shrink-0 fill-yellow-500" />
                      )}
                    </div>
                    {wf.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {wf.description}
                      </p>
                    )}
                  </div>

                  {/* 操作菜单 */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreVertical className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                      <DropdownMenuItem onClick={() => navigate(`/workflows/${wf.id}`)}>
                        <Pencil className="w-4 h-4 mr-2" />
                        编辑
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleToggle(wf)}>
                        {wf.is_active ? (
                          <>
                            <PowerOff className="w-4 h-4 mr-2" />
                            禁用
                          </>
                        ) : (
                          <>
                            <Power className="w-4 h-4 mr-2" />
                            启用
                          </>
                        )}
                      </DropdownMenuItem>
                      {!wf.is_default && (
                        <DropdownMenuItem onClick={() => handleSetDefault(wf)}>
                          <Star className="w-4 h-4 mr-2" />
                          设为默认
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => setDeleteDialogId(wf.id)}
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                {/* 标签行 */}
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="text-xs">
                    {APPROVAL_TYPE_LABELS[wf.approval_type] || wf.approval_type}
                  </Badge>
                  <Badge
                    variant={wf.is_active ? 'default' : 'secondary'}
                    className="text-xs"
                  >
                    {wf.is_active ? '已启用' : '已禁用'}
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    v{wf.version || 1}
                  </Badge>
                </div>

                {/* 节点数统计 */}
                {wf.definition?.steps && (
                  <p className="text-xs text-muted-foreground mt-2">
                    {wf.definition.steps.length} 个节点
                    {wf.definition.conditions ? ` / ${wf.definition.conditions.length} 个连接` : ''}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 删除确认对话框 */}
      <AlertDialog
        open={!!deleteDialogId}
        onOpenChange={(open) => !open && setDeleteDialogId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              此操作不可撤销。删除后，该流程将无法恢复。
              如果该流程正在使用中，请先禁用后再删除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default WorkflowList;
