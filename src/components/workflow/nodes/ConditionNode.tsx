import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { GitBranch } from 'lucide-react';
import { WorkflowNodeShell, workflowHandleClass } from './WorkflowNodeShell';

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
    <WorkflowNodeShell selected={selected} icon={GitBranch} typeLabel="条件分支" title={nodeData.label || '条件分支'} tone="warning" source={false}>
      <div className="font-mono text-[11px] text-muted-foreground">{conditionText}</div>
      {/* 左出口: 是 */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="yes"
        style={{ left: '30%' }}
        className={workflowHandleClass('success')}
      />
      <div
        className="absolute text-[10px] font-medium text-emerald-700 dark:text-emerald-300"
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
        className="!h-2.5 !w-2.5 !border-2 !border-background !bg-destructive"
      />
      <div
        className="absolute text-[10px] font-medium text-destructive"
        style={{ bottom: -16, left: '65%' }}
      >
        否
      </div>
    </WorkflowNodeShell>
  );
}

export const ConditionNode = memo(ConditionNodeComponent);
