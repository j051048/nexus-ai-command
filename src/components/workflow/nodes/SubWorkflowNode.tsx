import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { GitMerge } from 'lucide-react';

export interface SubWorkflowNodeData {
  label: string;
  workflow_id: string;
  workflow_name: string;
  [key: string]: unknown;
}

function SubWorkflowNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as SubWorkflowNodeData;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-indigo-500 ring-2 ring-indigo-500/20' : 'border-indigo-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-indigo-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-indigo-500/10">
          <GitMerge className="w-4 h-4 text-indigo-500" />
        </div>
        <span className="text-xs font-medium text-indigo-600">子流程节点</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '子流程'}</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        引用: {nodeData.workflow_name || '未选择'}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-indigo-500 !border-2 !border-background"
      />
    </div>
  );
}

export const SubWorkflowNode = memo(SubWorkflowNodeComponent);
