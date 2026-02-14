import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Zap } from 'lucide-react';

export interface AutoApproveNodeData {
  label: string;
  max_amount: number;
  [key: string]: unknown;
}

function AutoApproveNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as AutoApproveNodeData;

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-green-500 ring-2 ring-green-500/20' : 'border-green-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-green-500/10">
          <Zap className="w-4 h-4 text-green-500" />
        </div>
        <span className="text-xs font-medium text-green-600">自动审批</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '自动审批'}</div>
      {nodeData.max_amount > 0 && (
        <div className="text-xs text-muted-foreground mt-0.5">
          金额上限: {nodeData.max_amount}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-background"
      />
    </div>
  );
}

export const AutoApproveNode = memo(AutoApproveNodeComponent);
