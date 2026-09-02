import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { UserCircle2 } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

function InitiatorNodeComponent({ selected }: NodeProps) {
  return (
    <WorkflowNodeShell selected={selected} icon={UserCircle2} typeLabel="流程起点" title="发起人" tone="success" target={false}>
      <div className="text-[11px] text-muted-foreground">提交后从这里开始流转</div>
    </WorkflowNodeShell>
  );
}

export const InitiatorNode = memo(InitiatorNodeComponent);
