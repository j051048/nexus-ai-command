import { DragEvent } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UserCheck, GitBranch, Users, Zap, Bell, Mail, Timer, GitMerge, Info } from 'lucide-react';

interface NodeTypeConfig {
  type: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
}

const BASIC_NODES: NodeTypeConfig[] = [
  {
    type: 'approver',
    label: '审批人',
    description: '指定角色审批',
    icon: <UserCheck className="w-5 h-5" />,
    color: 'text-blue-500 bg-blue-500/10 border-blue-200',
  },
  {
    type: 'condition',
    label: '条件分支',
    description: '按金额/类型分流',
    icon: <GitBranch className="w-5 h-5" />,
    color: 'text-yellow-600 bg-yellow-500/10 border-yellow-200',
  },
  {
    type: 'auto_approve',
    label: '自动审批',
    description: '小额自动通过',
    icon: <Zap className="w-5 h-5" />,
    color: 'text-green-500 bg-green-500/10 border-green-200',
  },
  {
    type: 'notify',
    label: '通知',
    description: '发送通知消息',
    icon: <Bell className="w-5 h-5" />,
    color: 'text-gray-500 bg-gray-500/10 border-gray-200',
  },
];

const ADVANCED_NODES: NodeTypeConfig[] = [
  {
    type: 'parallel',
    label: '并行审批',
    description: '多人同时审批',
    icon: <Users className="w-5 h-5" />,
    color: 'text-purple-500 bg-purple-500/10 border-purple-200',
  },
  {
    type: 'cc_notify',
    label: '抄送',
    description: '抄送通知相关人员',
    icon: <Mail className="w-5 h-5" />,
    color: 'text-teal-500 bg-teal-500/10 border-teal-200',
  },
  {
    type: 'timer',
    label: '定时等待',
    description: '延迟后继续流转',
    icon: <Timer className="w-5 h-5" />,
    color: 'text-orange-500 bg-orange-500/10 border-orange-200',
  },
  {
    type: 'sub_workflow',
    label: '子流程',
    description: '引用其他审批流程',
    icon: <GitMerge className="w-5 h-5" />,
    color: 'text-indigo-500 bg-indigo-500/10 border-indigo-200',
  },
];

function NodeCard({ nodeType, onDragStart }: { nodeType: NodeTypeConfig; onDragStart: (e: DragEvent<HTMLDivElement>, type: string) => void }) {
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, nodeType.type)}
      className={`
        flex items-center gap-3 p-2.5 rounded-lg border cursor-grab
        hover:shadow-md transition-all active:cursor-grabbing
        ${nodeType.color}
      `}
    >
      <div className="flex-shrink-0">
        {nodeType.icon}
      </div>
      <div className="min-w-0">
        <div className="text-sm font-medium">{nodeType.label}</div>
        <div className="text-xs text-muted-foreground truncate">
          {nodeType.description}
        </div>
      </div>
    </div>
  );
}

export function WorkflowSidebar() {
  const onDragStart = (event: DragEvent<HTMLDivElement>, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <Card className="w-56 flex-shrink-0 h-full overflow-auto">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">节点面板</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {/* 快速上手提示 */}
        <div className="flex gap-2 p-2.5 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/50">
          <Info className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <div className="text-[11px] text-blue-700 dark:text-blue-300 leading-relaxed">
            <p className="font-medium mb-0.5">快速上手</p>
            <p>1. 拖拽节点到画布</p>
            <p>2. 从节点圆点拖出连线</p>
            <p>3. 点击节点编辑属性</p>
          </div>
        </div>

        {/* 基础节点 */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 px-0.5">
            常用节点
          </p>
          <div className="space-y-1.5">
            {BASIC_NODES.map((nodeType) => (
              <NodeCard key={nodeType.type} nodeType={nodeType} onDragStart={onDragStart} />
            ))}
          </div>
        </div>

        {/* 高级节点 */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2 px-0.5">
            高级节点
          </p>
          <div className="space-y-1.5">
            {ADVANCED_NODES.map((nodeType) => (
              <NodeCard key={nodeType.type} nodeType={nodeType} onDragStart={onDragStart} />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
