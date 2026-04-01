/**
 * 工作流流程图可视化组件
 * Phase 2: React Flow节点状态高亮
 */
import React from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { User, CheckCircle2, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

// 自定义审批节点
function ApprovalNode({ data }: { data: any }) {
  const statusStyles = {
    completed: 'bg-success/10 border-success/50 dark:bg-success/5',
    current: 'bg-primary/10 border-primary/50 dark:bg-primary/5 shadow-lg shadow-primary/20',
    pending: 'bg-muted/50 border-border dark:bg-muted/20',
  };

  const statusIcons = {
    completed: <CheckCircle2 className="w-4 h-4 text-success" />,
    current: <Clock className="w-4 h-4 text-primary animate-pulse" />,
    pending: <User className="w-4 h-4 text-muted-foreground" />,
  };

  return (
    <div className={cn(
      "approval-node p-4 rounded-xl border-2 transition-all duration-200",
      "hover:shadow-lg hover:scale-105 cursor-pointer",
      statusStyles[data.status || 'pending']
    )}>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-background flex items-center justify-center border">
          {statusIcons[data.status || 'pending']}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{data.label}</p>
          {data.approver && (
            <p className="text-xs text-muted-foreground truncate">{data.approver}</p>
          )}
        </div>
      </div>

      {data.status === 'completed' && data.completedAt && (
        <div className="mt-3 pt-3 border-t border-border/50 text-xs text-muted-foreground">
          {data.completedAt}
        </div>
      )}
    </div>
  );
}

// 自定义执行人节点
function ExecutorNode({ data }: { data: any }) {
  return (
    <div className="executor-node p-4 rounded-xl border-2 bg-purple-500/10 border-purple-500/50 dark:bg-purple-500/5 hover:shadow-lg transition-all cursor-pointer">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-background flex items-center justify-center border">
          <CheckCircle2 className="w-4 h-4 text-purple-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{data.label}</p>
          <p className="text-xs text-muted-foreground truncate">{data.actionLabel}</p>
        </div>
      </div>
      {data.status === 'completed' && data.evidence && (
        <div className="mt-3 pt-3 border-t border-border/50 text-xs text-purple-600 dark:text-purple-400">
          已确认 · <a href={data.evidence} className="underline hover:text-purple-700">查看凭证</a>
        </div>
      )}
    </div>
  );
}

// 自定义并行网关节点
function ParallelGatewayNode({ data }: { data: any }) {
  return (
    <div className="parallel-gateway p-3 rounded-xl border-2 bg-warning/10 border-warning/50 dark:bg-warning/5 hover:shadow-lg transition-all cursor-pointer">
      <div className="text-center">
        <p className="text-sm font-medium mb-1">
          {data.mode === 'all' ? '会签' : '或签'}
        </p>
        <p className="text-xs text-muted-foreground">
          {data.mode === 'all' ? '全部同意' : `${data.minApprovals}人同意`}
        </p>
      </div>
    </div>
  );
}

const nodeTypes = {
  approval: ApprovalNode,
  executor: ExecutorNode,
  parallel_gateway: ParallelGatewayNode,
};

interface WorkflowFlowProps {
  workflowData: {
    nodes: Node[];
    edges: Edge[];
  };
}

export function WorkflowFlow({ workflowData }: WorkflowFlowProps) {
  return (
    <div className="h-96 border rounded-lg">
      <ReactFlow
        nodes={workflowData.nodes}
        edges={workflowData.edges}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

// 示例用法
/*
const exampleWorkflow = {
  nodes: [
    { id: '1', type: 'approval', position: { x: 100, y: 100 }, data: { label: '主管审批', approver: '李主管', status: 'completed', completedAt: '10:30' } },
    { id: '2', type: 'approval', position: { x: 100, y: 200 }, data: { label: '财务审核', approver: '张会计', status: 'current' } },
    { id: '3', type: 'executor', position: { x: 100, y: 300 }, data: { label: '财务打款', actionLabel: '确认打款', status: 'pending' } },
  ],
  edges: [
    { id: 'e1-2', source: '1', target: '2', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e2-3', source: '2', target: '3', markerEnd: { type: MarkerType.ArrowClosed } },
  ],
};
*/