import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Users } from 'lucide-react';

export interface ParallelNodeData {
  label: string;
  parallel_count: number;
  [key: string]: unknown;
}

function ParallelNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ParallelNodeData;
  const count = nodeData.parallel_count || 2;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-purple-500 ring-2 ring-purple-500/20' : 'border-purple-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-purple-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-purple-500/10">
          <Users className="w-4 h-4 text-purple-500" />
        </div>
        <span className="text-xs font-medium text-purple-600">并行审批</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '并行审批'}</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        并行人数: {count}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-purple-500 !border-2 !border-background"
      />
    </div>
  );
}

export const ParallelNode = memo(ParallelNodeComponent);
