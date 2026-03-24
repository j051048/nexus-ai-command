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
        px-4 py-3 rounded-xl border-2 bg-background/95 backdrop-blur-sm shadow-lg min-w-[180px]
        ${selected ? 'border-purple-500 ring-4 ring-purple-500/20' : 'border-purple-400/50'}
        transition-all group relative overflow-hidden
      `}
    >
      {/* Decorative parallel bars on sides */}
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-purple-500/50" />
      <div className="absolute right-0 top-0 bottom-0 w-1 bg-purple-500/50" />

      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-purple-500 !border-2 !border-background scale-110"
      />

      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-purple-500/10">
            <Users className="w-4 h-4 text-purple-600" />
          </div>
          <span className="text-[10px] font-bold text-purple-600 uppercase tracking-wider">并行审批</span>
        </div>
        <div className="px-1.5 py-0.5 rounded-md bg-purple-100 dark:bg-purple-900/30 text-[10px] font-bold text-purple-600">
          {count}路
        </div>
      </div>

      <div className="text-sm font-bold tracking-tight">{nodeData.label || '并行审批'}</div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-purple-500 !border-2 !border-background scale-110"
      />
    </div>
  );
}

export const ParallelNode = memo(ParallelNodeComponent);
