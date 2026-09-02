import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { Zap } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface AutoApproveNodeData {
  label: string;
  max_amount: number;
  [key: string]: unknown;
}

function AutoApproveNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as AutoApproveNodeData;

  return (
    <WorkflowNodeShell selected={selected} icon={Zap} typeLabel="自动规则" title={nodeData.label || '自动审批'} tone="success">
      {nodeData.max_amount > 0 && (
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground">金额上限</span>
          <span className="font-medium tabular-nums">{nodeData.max_amount.toLocaleString()}</span>
        </div>
      )}
    </WorkflowNodeShell>
  );
}

export const AutoApproveNode = memo(AutoApproveNodeComponent);
