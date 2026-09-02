import type { DragEvent, ReactNode } from 'react';
import { UserCheck, GitBranch, Users, Zap, Bell, Mail, Timer, GitMerge, GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';

interface NodeTypeConfig {
  type: string;
  label: string;
  description: string;
  icon: ReactNode;
  tone: 'primary' | 'success' | 'warning' | 'info' | 'neutral';
}

const TONE_STYLES: Record<NodeTypeConfig['tone'], string> = {
  primary: 'border-primary/20 bg-primary/[0.08] text-primary',
  success: 'border-success/20 bg-success/[0.08] text-success',
  warning: 'border-warning/20 bg-warning/[0.08] text-warning',
  info: 'border-primary/15 bg-primary/[0.06] text-primary',
  neutral: 'border-border bg-muted/60 text-muted-foreground',
};

const BASIC_NODES: NodeTypeConfig[] = [
  {
    type: 'approver',
    label: '审批人',
    description: '指定角色审批',
    icon: <UserCheck className="w-5 h-5" />,
    tone: 'primary',
  },
  {
    type: 'condition',
    label: '条件分支',
    description: '按金额/类型分流',
    icon: <GitBranch className="w-5 h-5" />,
    tone: 'warning',
  },
  {
    type: 'auto_approve',
    label: '自动审批',
    description: '小额自动通过',
    icon: <Zap className="w-5 h-5" />,
    tone: 'success',
  },
  {
    type: 'notify',
    label: '通知',
    description: '发送通知消息',
    icon: <Bell className="w-5 h-5" />,
    tone: 'neutral',
  },
];

const ADVANCED_NODES: NodeTypeConfig[] = [
  {
    type: 'parallel',
    label: '并行审批',
    description: '多人同时审批',
    icon: <Users className="w-5 h-5" />,
    tone: 'info',
  },
  {
    type: 'cc_notify',
    label: '抄送',
    description: '抄送通知相关人员',
    icon: <Mail className="w-5 h-5" />,
    tone: 'neutral',
  },
  {
    type: 'timer',
    label: '定时等待',
    description: '延迟后继续流转',
    icon: <Timer className="w-5 h-5" />,
    tone: 'warning',
  },
  {
    type: 'sub_workflow',
    label: '子流程',
    description: '引用其他审批流程',
    icon: <GitMerge className="w-5 h-5" />,
    tone: 'info',
  },
];

function NodeCard({ nodeType, onDragStart }: { nodeType: NodeTypeConfig; onDragStart: (e: DragEvent<HTMLDivElement>, type: string) => void }) {
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, nodeType.type)}
      className="group flex cursor-grab items-center gap-2.5 rounded-md border border-transparent px-2 py-2 transition-[background-color,border-color] duration-150 hover:border-border hover:bg-background active:cursor-grabbing"
    >
      <div className={cn('flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border [&_svg]:h-4 [&_svg]:w-4', TONE_STYLES[nodeType.tone])}>
        {nodeType.icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{nodeType.label}</div>
        <div className="truncate text-[11px] text-muted-foreground">
          {nodeType.description}
        </div>
      </div>
      <GripVertical className="h-4 w-4 text-muted-foreground/50 opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  );
}

export function WorkflowSidebar() {
  const onDragStart = (event: DragEvent<HTMLDivElement>, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <aside className="h-full w-60 flex-shrink-0 overflow-auto border-r bg-card/55" aria-label="流程节点">
      <div className="border-b px-4 py-3">
        <h2 className="text-sm font-semibold">添加节点</h2>
        <p className="mt-0.5 text-[11px] text-muted-foreground">拖入画布后连接端口</p>
      </div>
      <div className="space-y-5 p-3">
        {/* 基础节点 */}
        <div>
          <p className="mb-1.5 px-2 text-[11px] font-medium text-muted-foreground">
            常用节点
          </p>
          <div className="space-y-0.5">
            {BASIC_NODES.map((nodeType) => (
              <NodeCard key={nodeType.type} nodeType={nodeType} onDragStart={onDragStart} />
            ))}
          </div>
        </div>

        {/* 高级节点 */}
        <div>
          <p className="mb-1.5 px-2 text-[11px] font-medium text-muted-foreground">
            高级节点
          </p>
          <div className="space-y-0.5">
            {ADVANCED_NODES.map((nodeType) => (
              <NodeCard key={nodeType.type} nodeType={nodeType} onDragStart={onDragStart} />
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
