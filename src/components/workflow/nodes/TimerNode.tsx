import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Timer } from 'lucide-react';

export interface TimerNodeData {
  label: string;
  wait_hours: number;
  auto_advance: boolean;
  [key: string]: unknown;
}

function TimerNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as TimerNodeData;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-orange-500 ring-2 ring-orange-500/20' : 'border-orange-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-orange-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-orange-500/10">
          <Timer className="w-4 h-4 text-orange-500" />
        </div>
        <span className="text-xs font-medium text-orange-600">等待节点</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '定时等待'}</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        等待: {nodeData.wait_hours || 0} 小时
      </div>
      {nodeData.auto_advance && (
        <div className="text-xs text-orange-500 mt-0.5">超时自动推进</div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-orange-500 !border-2 !border-background"
      />
    </div>
  );
}

export const TimerNode = memo(TimerNodeComponent);
