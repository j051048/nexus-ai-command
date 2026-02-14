import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Bell } from 'lucide-react';

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
    <div
      className={`
        px-4 py-3 rounded-lg border-2 bg-background shadow-sm min-w-[160px]
        ${selected ? 'border-gray-500 ring-2 ring-gray-500/20' : 'border-gray-400'}
        transition-all
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-500 !border-2 !border-background"
      />

      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 rounded-md bg-gray-500/10">
          <Bell className="w-4 h-4 text-gray-500" />
        </div>
        <span className="text-xs font-medium text-gray-600">通知节点</span>
      </div>

      <div className="text-sm font-semibold">{nodeData.label || '发送通知'}</div>
      <div className="text-xs text-muted-foreground mt-0.5">
        渠道: {channelText}
      </div>
      {nodeData.template && (
        <div className="text-xs text-muted-foreground">
          模板: {nodeData.template}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-gray-500 !border-2 !border-background"
      />
    </div>
  );
}

export const NotifyNode = memo(NotifyNodeComponent);
