import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { Mail } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface CcNotifyNodeData {
  label: string;
  recipients: string[];
  message: string;
  [key: string]: unknown;
}

function CcNotifyNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as CcNotifyNodeData;
  const recipients = nodeData.recipients || [];

  const recipientText = recipients.length > 0
    ? recipients.length > 2
      ? `${recipients.slice(0, 2).join('、')} 等${recipients.length}人`
      : recipients.join('、')
    : '未配置';

  return (
    <WorkflowNodeShell selected={selected} icon={Mail} typeLabel="抄送通知" title={nodeData.label || '抄送通知'} tone="neutral">
      <div className="flex items-center justify-between gap-3 text-[11px]"><span className="text-muted-foreground">接收人</span><span className="max-w-28 truncate font-medium">{recipientText}</span></div>
      {nodeData.message && (
        <div className="mt-1 truncate text-[11px] text-muted-foreground" title={nodeData.message}>{nodeData.message}</div>
      )}
    </WorkflowNodeShell>
  );
}

export const CcNotifyNode = memo(CcNotifyNodeComponent);
