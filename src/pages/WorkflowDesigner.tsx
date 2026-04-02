import { useState, useRef, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ReactFlowProvider } from '@xyflow/react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  ArrowLeft,
  Save,
  Pencil,
  Check,
  Loader2,
  Monitor,
} from 'lucide-react';
import { toast } from 'sonner';

import { WorkflowCanvas, type WorkflowCanvasRef } from '@/components/workflow/WorkflowCanvas';
import { WorkflowSidebar } from '@/components/workflow/WorkflowSidebar';
import { useIsMobile } from '@/hooks/use-mobile';
import { WorkflowProperties } from '@/components/workflow/WorkflowProperties';
import {
  useWorkflow,
  useCreateWorkflow,
  useUpdateWorkflow,
} from '@/hooks/useWorkflows';
import type { Node } from '@xyflow/react';

// 审批类型选项
const APPROVAL_TYPES = [
  { value: 'expense', label: '费用报销' },
  { value: 'purchase', label: '采购申请' },
  { value: 'leave', label: '请假审批' },
  { value: 'travel', label: '出差申请' },
  { value: 'contract', label: '合同审批' },
  { value: 'general', label: '通用审批' },
];

export function WorkflowDesigner() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';
  const isMobile = useIsMobile();

  // State
  const [workflowName, setWorkflowName] = useState('新建流程');
  const [description, setDescription] = useState('');
  const [approvalType, setApprovalType] = useState('general');
  const [isEditingName, setIsEditingName] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // Refs
  const canvasRef = useRef<WorkflowCanvasRef>(null);

  // Data hooks
  const { data: workflow, isLoading: isLoadingWorkflow } = useWorkflow(id);
  const createMutation = useCreateWorkflow();
  const updateMutation = useUpdateWorkflow();

  const isSaving = createMutation.isPending || updateMutation.isPending;

  // Load existing workflow
  useEffect(() => {
    if (workflow && canvasRef.current) {
      setWorkflowName(workflow.name);
      setDescription(workflow.description || '');
      setApprovalType(workflow.approval_type || 'general');
      canvasRef.current.loadWorkflowData(workflow.definition);
    }
  }, [workflow]);

  // Handle node selection
  const handleNodeSelect = useCallback((node: Node | null) => {
    setSelectedNode(node);
  }, []);

  // Handle node data update from properties panel
  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Record<string, unknown>) => {
      // Update the canvas nodes
      if (canvasRef.current) {
        const currentData = canvasRef.current.getWorkflowData();
        const updatedSteps = currentData.steps.map((step) => {
          if (step.id === nodeId) {
            // 修复：直接合并 data，不要拆分 label 和 config
            return {
              ...step,
              label: (data.label as string) || step.label,
              config: { ...step.config, ...data }, // 保留所有配置
            };
          }
          return step;
        });
        canvasRef.current.loadWorkflowData({
          steps: updatedSteps,
          conditions: currentData.conditions,
        });
      }

      // Update selected node reference
      setSelectedNode((prev) =>
        prev && prev.id === nodeId ? { ...prev, data: { ...data } } : prev
      );
    },
    []
  );

  // Save workflow
  const handleSave = useCallback(async () => {
    if (!canvasRef.current) return;

    const definition = canvasRef.current.getWorkflowData();

    if (definition.steps.filter((s) => s.type !== 'initiator' && s.type !== 'end').length === 0) {
      toast.error('请至少添加一个流程节点');
      return;
    }

    if (!workflowName.trim()) {
      toast.error('请输入流程名称');
      return;
    }

    try {
      if (isNew) {
        const result = await createMutation.mutateAsync({
          name: workflowName,
          description,
          approval_type: approvalType,
          definition,
        });
        toast.success('流程创建成功');
        if (result?.id) {
          navigate(`/workflows/${result.id}`, { replace: true });
        }
      } else {
        await updateMutation.mutateAsync({
          id: id!,
          name: workflowName,
          description,
          approval_type: approvalType,
          definition,
        });
        toast.success('流程保存成功');
      }
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : '保存失败，请重试'
      );
    }
  }, [
    isNew,
    id,
    workflowName,
    description,
    approvalType,
    createMutation,
    updateMutation,
    navigate,
  ]);

  // 移动端降级：流程设计器需要桌面端操作（放在所有 hooks 之后，遵守 Rules of Hooks）
  if (isMobile) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <Monitor className="w-16 h-16 text-muted-foreground/40 mb-4" />
        <h2 className="text-lg font-semibold mb-2">流程设计器</h2>
        <p className="text-sm text-muted-foreground mb-4">
          流程设计需要在桌面端操作，移动端暂不支持画布拖拽编辑。
        </p>
        <p className="text-xs text-muted-foreground mb-6">
          请使用电脑浏览器访问以获得完整体验。
        </p>
        <Button variant="outline" onClick={() => navigate('/workflows')}>
          查看流程列表
        </Button>
      </div>
    );
  }

  if (!isNew && isLoadingWorkflow) {
    return (
      <div className="flex items-center justify-center h-[calc(100dvh-200px)]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <div className="flex flex-col h-[calc(100dvh-120px)]">
        {/* 顶部工具栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-background">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/workflows')}
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>

            {/* 流程名称 */}
            {isEditingName ? (
              <div className="flex items-center gap-2">
                <Input
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  className="h-8 w-56 text-sm"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') setIsEditingName(false);
                  }}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setIsEditingName(false)}
                >
                  <Check className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div
                className="flex items-center gap-2 cursor-pointer group"
                onClick={() => setIsEditingName(true)}
              >
                <h2 className="text-lg font-semibold">{workflowName}</h2>
                <Pencil className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            )}

            <Badge variant="outline" className="text-xs">
              {isNew ? '新建' : `v${workflow?.version || 1}`}
            </Badge>
          </div>

          <div className="flex items-center gap-3">
            {/* 适用类型 */}
            <Select value={approvalType} onValueChange={setApprovalType}>
              <SelectTrigger className="h-8 w-32 text-sm">
                <SelectValue placeholder="审批类型" />
              </SelectTrigger>
              <SelectContent>
                {APPROVAL_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* 描述 */}
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="流程描述 (可选)"
              className="h-8 w-48 text-sm"
            />

            {/* 保存 */}
            <Button
              onClick={handleSave}
              disabled={isSaving}
              size="sm"
              className="gap-2"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              保存
            </Button>
          </div>
        </div>

        {/* 主体区域 */}
        <div className="flex flex-1 overflow-hidden">
          {/* 左侧节点面板 */}
          <WorkflowSidebar />

          {/* 中间画布 */}
          <WorkflowCanvas
            ref={canvasRef}
            onNodeSelect={handleNodeSelect}
            onNodeUpdate={handleNodeUpdate}
          />

          {/* 右侧属性面板 */}
          <WorkflowProperties
            selectedNode={selectedNode}
            onNodeUpdate={handleNodeUpdate}
          />
        </div>
      </div>
    </ReactFlowProvider>
  );
}

export default WorkflowDesigner;
