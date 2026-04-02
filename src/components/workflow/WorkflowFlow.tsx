/**
 * 工作流流程图可视化组件
 * Phase 2: React Flow节点状态高亮
 */
import React from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface NodeData {
  status?: 'completed' | 'current' | 'pending';
  label: string;
  approver?: string;
  completedAt?: string;
  actionLabel?: string;
  evidence?: string;
  mode?: 'all' | 'one';
  minApprovals?: number;
}

// 自定义审批节点
function ApprovalNode({ data }: { data: NodeData }) {
  const statusColor: Record<string, string> = {
    completed: 'bg-green-100 border-green-500',
    current: 'bg-blue-100 border-blue-500',
    pending: 'bg-gray-50 border-gray-300',
  };

  return (
    <div className={`approval-node p-4 rounded-lg border-2 ${statusColor[data.status || 'pending']}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center">
          👤
        </div>
        <div>
          <p className="text-sm font-medium">{data.label}</p>
          {data.approver && <p className="text-xs text-gray-500">{data.approver}</p>}
        </div>
      </div>
      {data.status === 'current' && (
        <div className="mt-2 text-xs text-blue-600">待处理</div>
      )}
      {data.status === 'completed' && (
        <div className="mt-2 text-xs text-green-600">已完成 {data.completedAt}</div>
      )}
    </div>
  );
}

// 自定义执行人节点
function ExecutorNode({ data }: { data: NodeData }) {
  return (
    <div className="executor-node p-4 rounded-lg border-2 bg-purple-50 border-purple-500">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center">
          ✅
        </div>
        <div>
          <p className="text-sm font-medium">{data.label}</p>
          <p className="text-xs text-gray-500">{data.actionLabel}</p>
        </div>
      </div>
      {data.status === 'completed' && data.evidence && (
        <div className="mt-2 text-xs text-purple-600">
          已确认 · <a href={data.evidence} className="underline">查看凭证</a>
        </div>
      )}
    </div>
  );
}

// 自定义并行网关节点
function ParallelGatewayNode({ data }: { data: NodeData }) {
  return (
    <div className="parallel-gateway p-3 rounded-lg border-2 bg-yellow-50 border-yellow-500">
      <div className="text-center">
        <p className="text-sm font-medium mb-1">
          {data.mode === 'all' ? '会签' : '或签'}
        </p>
        <p className="text-xs text-gray-500">
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