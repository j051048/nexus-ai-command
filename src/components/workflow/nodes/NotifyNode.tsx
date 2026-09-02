import { memo } from 'react';
import { type NodeProps } from '@xyflow/react';
import { Bell } from 'lucide-react';
import { WorkflowNodeShell } from './WorkflowNodeShell';

export interface NotifyNodeData {
  label: string;
  channels: string[];
  template: string;
  [key: string]: unknown;
}

const CHANNEL_LABELS: Record<string, string> = {
  email: '邮件',
  wechat_work: '企微',
  dingtalk: '钉钉',
  sms: '短信',
};

function NotifyNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as NotifyNodeData;
  const channels = nodeData.channels || [];

  const channelText = channels.length > 0
    ? channels.map((c) => CHANNEL_LABELS[c] || c).join('、')
    : '未配置';

  return (
    <WorkflowNodeShell selected={selected} icon={Bell} typeLabel="消息通知" title={nodeData.label || '发送通知'} tone="neutral">
      <div className="flex items-center justify-between gap-3 text-[11px]"><span className="text-muted-foreground">渠道</span><span className="font-medium">{channelText}</span></div>
      {nodeData.template && (
        <div className="mt-1 truncate text-[11px] text-muted-foreground">模板：{nodeData.template}</div>
      )}
    </WorkflowNodeShell>
  );
}

export const NotifyNode = memo(NotifyNodeComponent);
