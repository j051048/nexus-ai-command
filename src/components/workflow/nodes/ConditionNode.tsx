import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { GitBranch } from 'lucide-react';

export interface ConditionNodeData {
  label: string;
  field: string;
  operator: string;
  value: string;
  [key: string]: unknown;
}

const OPERATOR_LABELS: Record<string, string> = {
  gt: '>',
  gte: '>=',
  lt: '<',
  lte: '<=',
  eq: '=',
  neq: '!=',
};

function ConditionNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ConditionNodeData;
  const opLabel = OPERATOR_LABELS[nodeData.operator] || nodeData.operator || '>';

  const conditionText = nodeData.field && nodeData.value
    ? `${nodeData.field} ${opLabel} ${nodeData.value}`
    : nodeData.label || '条件分支';

  return (
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background/90 backdrop-blur-sm shadow-xl min-w-[180px]
        ${selected ? 'border-yellow-500 ring-4 ring-yellow-500/20' : 'border-yellow-400/60'}
        transition-all duration-300
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-yellow-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-yellow-500/10">
          <GitBranch className="w-4 h-4 text-yellow-600" />
        </div>
        <span className="text-xs font-medium text-yellow-600">条件分支</span>
      </div>

      <div className="text-sm font-semibold">{conditionText}</div>

      {/* 左出口: 是 */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="yes"
        style={{ left: '30%' }}
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-background"
      />
      <div
        className="absolute text-[10px] text-green-600 font-medium"
        style={{ bottom: -16, left: '25%' }}
      >
        是
      </div>

      {/* 右出口: 否 */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="no"
        style={{ left: '70%' }}
        className="!w-3 !h-3 !bg-red-500 !border-2 !border-background"
      />
      <div
        className="absolute text-[10px] text-red-600 font-medium"
        style={{ bottom: -16, left: '65%' }}
      >
        否
      </div>
    </div>
  );
}

export const ConditionNode = memo(ConditionNodeComponent);
