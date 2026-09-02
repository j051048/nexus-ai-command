import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { CircleCheckBig } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

function EndNodeComponent({ selected }: NodeProps) {
  return (
    <WorkflowNodeShell selected={selected} icon={CircleCheckBig} typeLabel="流程终点" title="结束" tone="neutral" source={false}>
      <div className="text-[11px] text-muted-foreground">完成并通知发起人</div>
    </WorkflowNodeShell>
  );
}

export const EndNode = memo(EndNodeComponent);
