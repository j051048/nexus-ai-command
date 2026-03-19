import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { UserCircle2 } from 'lucide-react';

function InitiatorNodeComponent({ selected }: NodeProps) {
  return (
    <div
      className={`
        px-5 py-3 rounded-full border-2 bg-background shadow-sm min-w-[140px] text-center
        ${selected ? 'border-primary ring-2 ring-primary/20' : 'border-green-400'}
        transition-all
      `}
    >
      <div className="flex items-center justify-center gap-2">
        <div className="p-1.5 rounded-full bg-green-500/10">
          <UserCircle2 className="w-4 h-4 text-green-600" />
        </div>
        <div>
          <div className="text-sm font-semibold text-green-700">发起人</div>
          <div className="text-[10px] text-muted-foreground">流程从这里开始</div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-background"
      />
    </div>
  );
}

export const InitiatorNode = memo(InitiatorNodeComponent);
