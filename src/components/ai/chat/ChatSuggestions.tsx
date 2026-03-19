import React, { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  History,
  Zap,
  Lightbulb,
  Keyboard,
  CheckCircle,
  Bell,
} from 'lucide-react';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { useUnreadCount } from '@/hooks/useNotificationCenter';

interface QuickReply {
  id: string;
  text: string;
  icon?: React.ReactNode;
}

interface ChatSuggestionsProps {
  showQuickReplies: boolean;
  messagesCount: number;
  onQuickReply: (reply: QuickReply) => void;
}

export function ChatSuggestions({
  showQuickReplies,
  messagesCount,
  onQuickReply,
}: ChatSuggestionsProps) {
  const { data: approvalCount } = usePendingApprovalsCount();
  const { data: unreadCount } = useUnreadCount();

  const quickReplies = useMemo<QuickReply[]>(() => {
    const items: QuickReply[] = [];

    if (approvalCount && approvalCount > 0) {
      items.push({
        id: 'approvals',
        text: `${approvalCount} 条待审批`,
        icon: <CheckCircle className="w-3 h-3" />,
      });
    }
    if (unreadCount && unreadCount > 0) {
      items.push({
        id: 'notifications',
        text: `${unreadCount} 条未读通知`,
        icon: <Bell className="w-3 h-3" />,
      });
    }

    // 静态兜底，保证至少有内容
    items.push(
      { id: 'todo', text: '查看今日待办', icon: <History className="w-3 h-3" /> },
      { id: 'sales', text: '本周销售汇总', icon: <Zap className="w-3 h-3" /> },
    );

    // 没有动态数据时补充更多静态项
    if (items.length <= 2) {
      items.push(
        { id: 'opportunity', text: '分析商机进度', icon: <Lightbulb className="w-3 h-3" /> },
        { id: 'help', text: '帮助指南', icon: <Keyboard className="w-3 h-3" /> },
      );
    }

    return items.slice(0, 4);
  }, [approvalCount, unreadCount]);

  if (!showQuickReplies || messagesCount > 1) return null;

  return (
    <div className="px-4 md:px-6 py-2 border-t border-border/50">
      <p className="text-xs text-muted-foreground mb-2">快捷指令</p>
      <div className="flex flex-wrap gap-2">
        {quickReplies.map((reply) => (
          <Button
            key={reply.id}
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={() => onQuickReply(reply)}
          >
            {reply.icon}
            <span className="ml-1.5">{reply.text}</span>
          </Button>
        ))}
      </div>
    </div>
  );
}
