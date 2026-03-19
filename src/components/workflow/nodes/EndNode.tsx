import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { CircleCheckBig } from 'lucide-react';

function EndNodeComponent({ selected }: NodeProps) {
  return (
    <div
      className={`
        px-5 py-3 rounded-full border-2 bg-background shadow-sm min-w-[140px] text-center
        ${selected ? 'border-primary ring-2 ring-primary/20' : 'border-red-300'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-red-400 !border-2 !border-background"
      />

      <div className="flex items-center justify-center gap-2">
        <div className="p-1.5 rounded-full bg-red-500/10">
          <CircleCheckBig className="w-4 h-4 text-red-500" />
        </div>
        <div>
          <div className="text-sm font-semibold text-red-600">结束</div>
          <div className="text-[10px] text-muted-foreground">流程在此完成</div>
        </div>
      </div>
    </div>
  );
}

export const EndNode = memo(EndNodeComponent);
