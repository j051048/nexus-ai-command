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
  Command,
} from 'lucide-react';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { useUnreadCount } from '@/hooks/useNotificationCenter';
import { useSavedPrompts } from '@/hooks/useSavedPrompts';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

interface QuickReply {
  id: string;
  text: string;
  icon?: React.ReactNode;
  color?: string;
}

interface SavedPrompt {
  id: string;
  title: string;
  prompt: string;
}

interface ChatSuggestionsProps {
  showQuickReplies: boolean;
  messagesCount: number;
  onQuickReply: (reply: QuickReply) => void;
  followUpSuggestions?: string[];
}

export const ChatSuggestions = React.memo(function ChatSuggestions({
  showQuickReplies,
  messagesCount,
  onQuickReply,
  followUpSuggestions,
}: ChatSuggestionsProps) {
  const { data: approvalCount } = usePendingApprovalsCount();
  const { data: unreadCount } = useUnreadCount();
  const { prompts, deletePrompt } = useSavedPrompts();
  const { confirm, ConfirmDialog } = useConfirmDialog();
  
  // Ensure we have an array for prompts (safeguard against complex return types)
  const savedPrompts = Array.isArray(prompts) ? prompts as SavedPrompt[] : [];

  const quickReplies = useMemo<QuickReply[]>(() => {
    const items: QuickReply[] = [];

    if (approvalCount && approvalCount > 0) {
      items.push({
        id: 'approvals',
        text: `${approvalCount} 条待审批`,
        icon: <CheckCircle className="w-3 h-3" />,
        color: 'text-orange-500 bg-orange-500/10 border-orange-500/20',
      });
    }
    if (unreadCount && unreadCount > 0) {
      items.push({
        id: 'notifications',
        text: `${unreadCount} 条未读通知`,
        icon: <Bell className="w-3 h-3" />,
        color: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
      });
    }

    items.push(
      { id: 'todo', text: '查看今日待办', icon: <History className="w-3 h-3" />, color: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20' },
      { id: 'sales', text: '本周销售汇总', icon: <Zap className="w-3 h-3" />, color: 'text-amber-500 bg-amber-500/10 border-amber-500/20' },
    );

    if (items.length <= 2) {
      items.push(
        { id: 'opportunity', text: '分析商机进度', icon: <Lightbulb className="w-3 h-3" />, color: 'text-sky-500 bg-sky-500/10 border-sky-500/20' },
        { id: 'help', text: '帮助指南', icon: <Keyboard className="w-3 h-3" />, color: 'text-purple-500 bg-purple-500/10 border-purple-500/20' },
      );
    }

    return items.slice(0, 4);
  }, [approvalCount, unreadCount]);

  const showSavedSuggestions = savedPrompts.length > 0;
  const showBuiltinReplies = showQuickReplies;
  const hasFollowUps = followUpSuggestions && followUpSuggestions.length > 0;

  if (!showBuiltinReplies && !showSavedSuggestions && !hasFollowUps) return null;

  return (
    <div className="py-3 overflow-hidden">
      <div className="flex flex-col gap-3">
        {/* Header decoration */}
        <div className="flex items-center gap-2 px-4 md:px-6">
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border/50 to-transparent" />
          <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/50">
            <Command className="w-3 h-3" />
            智能建议
          </span>
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border/50 to-transparent" />
        </div>

        <div className="relative group">
          <div className="flex overflow-x-auto scrollbar-none gap-2 px-4 md:px-6 pb-2">
            <AnimatePresence mode="popLayout">
              {showBuiltinReplies && quickReplies.map((reply) => (
                <motion.div
                  key={reply.id}
                  initial={{ opacity: 0, scale: 0.9, y: 5 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  whileHover={{ y: -2 }}
                >
                  <Button
                    variant="outline"
                    size="sm"
                    className={cn(
                      "h-8 rounded-full border px-4 text-[11px] shadow-sm transition-all whitespace-nowrap",
                      reply.color || "bg-background border-border"
                    )}
                    onClick={() => onQuickReply(reply)}
                  >
                    {reply.icon && <span className="mr-1.5">{reply.icon}</span>}
                    {reply.text}
                  </Button>
                </motion.div>
              ))}

              {showSavedSuggestions && savedPrompts.slice(0, 6).map((sp: SavedPrompt) => (
                <motion.div
                  key={sp.id}
                  className="relative group/prompt"
                  initial={{ opacity: 0, scale: 0.9, y: 5 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  whileHover={{ y: -2 }}
                >
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 rounded-full border border-primary/20 bg-primary/5 px-4 pr-8 text-[11px] text-primary shadow-sm hover:bg-primary/10 whitespace-nowrap"
                    onClick={() => onQuickReply({ id: sp.id, text: sp.prompt })}
                  >
                    <Bookmark className="mr-1.5 h-3 w-3" />
                    {sp.title}
                  </Button>
                  <button
                    className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover/prompt:opacity-100 transition-opacity text-primary/40 hover:text-destructive p-0.5"
                    onClick={async (e) => {
                      e.stopPropagation();
                      const ok = await confirm({
                        title: '确认删除',
                        description: `确定要删除快捷指令 "${sp.title}" 吗？此操作不可撤销。`,
                        variant: 'destructive'
                      });
                      if (ok) deletePrompt(sp.id);
                    }}
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </motion.div>
              ))}

              {hasFollowUps && followUpSuggestions!.map((suggestion, i) => (
                <motion.div
                   key={`followup-${i}`}
                   initial={{ opacity: 0, scale: 0.9, y: 5 }}
                   animate={{ opacity: 1, scale: 1, y: 0 }}
                   whileHover={{ y: -2 }}
                >
                  <Button
                    variant="secondary"
                    size="sm"
                    className="h-8 rounded-full border border-primary/10 bg-muted/50 px-4 text-[11px] shadow-sm transition-all hover:bg-muted whitespace-nowrap"
                    onClick={() => onQuickReply({ id: `followup-${i}`, text: suggestion })}
                  >
                    <Sparkles className="mr-1.5 h-3 w-3 text-primary" />
                    <span className="max-w-[180px] truncate">{suggestion}</span>
                  </Button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>
      {ConfirmDialog}
    </div>
  );
});
