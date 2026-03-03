import React from 'react';
import { Button } from '@/components/ui/button';
import {
  History,
  Zap,
  Lightbulb,
  Keyboard,
} from 'lucide-react';

interface QuickReply {
  id: string;
  text: string;
  icon?: React.ReactNode;
}

const defaultQuickReplies: QuickReply[] = [
  { id: '1', text: '查看今日待办', icon: <History className="w-3 h-3" /> },
  { id: '2', text: '本周销售汇总', icon: <Zap className="w-3 h-3" /> },
  { id: '3', text: '分析商机进度', icon: <Lightbulb className="w-3 h-3" /> },
  { id: '4', text: '帮助指南', icon: <Keyboard className="w-3 h-3" /> },
];

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
  if (!showQuickReplies || messagesCount > 1) return null;

  return (
    <div className="px-4 md:px-6 py-2 border-t border-border/50">
      <p className="text-xs text-muted-foreground mb-2">快捷指令</p>
      <div className="flex flex-wrap gap-2">
        {defaultQuickReplies.map((reply) => (
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
