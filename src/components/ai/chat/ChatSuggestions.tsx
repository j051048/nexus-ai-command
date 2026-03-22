import React, { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  History,
  Zap,
  Lightbulb,
  Keyboard,
  CheckCircle,
  Bell,
  Bookmark,
  X,
  Sparkles,
} from 'lucide-react';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { useUnreadCount } from '@/hooks/useNotificationCenter';
import { useSavedPrompts } from '@/hooks/useSavedPrompts';

interface QuickReply {
  id: string;
  text: string;
  icon?: React.ReactNode;
}

interface ChatSuggestionsProps {
  showQuickReplies: boolean;
  messagesCount: number;
  onQuickReply: (reply: QuickReply) => void;
  followUpSuggestions?: string[];
}

export function ChatSuggestions({
  showQuickReplies,
  messagesCount,
  onQuickReply,
  followUpSuggestions,
}: ChatSuggestionsProps) {
  const { data: approvalCount } = usePendingApprovalsCount();
  const { data: unreadCount } = useUnreadCount();
  const { prompts: savedPrompts, deletePrompt } = useSavedPrompts();

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

  // Show saved prompts section if user has any (visible up to 3 messages)
  const showSavedPrompts = savedPrompts.length > 0 && messagesCount <= 3;
  // Show quick replies only in initial state
  const showBuiltinReplies = showQuickReplies && messagesCount <= 1;
  const hasFollowUps = followUpSuggestions && followUpSuggestions.length > 0;

  if (!showBuiltinReplies && !showSavedPrompts && !hasFollowUps) return null;

  return (
    <div className="px-4 md:px-6 py-2 border-t border-border/50">
      {showBuiltinReplies && (
        <>
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
        </>
      )}

      {showSavedPrompts && (
        <div className={showBuiltinReplies ? 'mt-3 pt-2 border-t border-border/30' : ''}>
          <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
            <Bookmark className="w-3 h-3" />
            我的快捷指令
          </p>
          <div className="flex flex-wrap gap-2">
            {savedPrompts.slice(0, 6).map((sp) => (
              <div key={sp.id} className="group relative">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs pr-6"
                  onClick={() => onQuickReply({ id: sp.id, text: sp.prompt })}
                >
                  <Zap className="w-3 h-3" />
                  <span className="ml-1.5">{sp.title}</span>
                </Button>
                <button
                  className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    deletePrompt(sp.id);
                  }}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasFollowUps && (
        <div className={(showBuiltinReplies || showSavedPrompts) ? 'mt-3 pt-2 border-t border-border/30' : ''}>
          <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            继续追问
          </p>
          <div className="flex flex-wrap gap-2">
            {followUpSuggestions!.map((suggestion, i) => (
              <Button
                key={i}
                variant="outline"
                size="sm"
                className="h-auto py-1.5 px-3 text-xs text-left whitespace-normal max-w-[280px]"
                onClick={() => onQuickReply({ id: `followup-${i}`, text: suggestion })}
              >
                <Sparkles className="w-3 h-3 flex-shrink-0 mr-1.5" />
                {suggestion}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
