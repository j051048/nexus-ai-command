/**
 * PageAIEmbed — 页面级 AI 主动建议组件
 * 在页面空态或初始加载时展示 AI 生成的主动建议卡片
 */

import React from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Sparkles,
  X,
  ArrowRight,
  MessageSquare,
  ExternalLink,
  Zap,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
} from 'lucide-react';
import { usePageSuggestions, type PageSuggestion } from '@/hooks/usePageSuggestions';
import { useNavigate } from 'react-router-dom';

interface PageAIEmbedProps {
  page: string;
  context?: Record<string, unknown>;
  onChatAction?: (prompt: string) => void;
  onExecuteAction?: (actionId: string) => void;
  className?: string;
}

const priorityStyles: Record<string, string> = {
  high: 'border-l-4 border-l-destructive/60',
  medium: 'border-l-4 border-l-warning/60',
  low: 'border-l-4 border-l-primary/40',
};

const priorityIcons: Record<string, React.ReactNode> = {
  high: <AlertTriangle className="w-4 h-4 text-destructive" />,
  medium: <TrendingUp className="w-4 h-4 text-warning" />,
  low: <Sparkles className="w-4 h-4 text-primary" />,
};

function SuggestionCard({
  suggestion,
  onAction,
  onDismiss,
}: {
  suggestion: PageSuggestion;
  onAction: (s: PageSuggestion) => void;
  onDismiss: (id: string) => void;
}) {
  return (
    <Card
      className={cn(
        'relative group hover:shadow-md transition-all duration-200',
        priorityStyles[suggestion.priority] ?? priorityStyles.low,
      )}
    >
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-2 right-2 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => {
          e.stopPropagation();
          onDismiss(suggestion.id);
        }}
        aria-label="忽略建议"
      >
        <X className="h-3 w-3" />
      </Button>

      <CardContent className="pt-4 pb-3 px-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 shrink-0">
            {priorityIcons[suggestion.priority] ?? priorityIcons.low}
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-foreground leading-tight mb-1">
              {suggestion.title}
            </h4>
            <p className="text-xs text-muted-foreground leading-relaxed mb-3">
              {suggestion.description}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs gap-1.5"
              onClick={() => onAction(suggestion)}
            >
              {suggestion.actionType === 'chat' && <MessageSquare className="w-3 h-3" />}
              {suggestion.actionType === 'navigate' && <ExternalLink className="w-3 h-3" />}
              {suggestion.actionType === 'execute' && <Zap className="w-3 h-3" />}
              {suggestion.actionLabel}
              <ArrowRight className="w-3 h-3" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2].map((i) => (
        <Card key={i}>
          <CardContent className="pt-4 pb-3 px-4">
            <div className="flex items-start gap-3">
              <Skeleton className="w-4 h-4 rounded mt-0.5" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-7 w-24" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function PageAIEmbed({
  page,
  context,
  onChatAction,
  onExecuteAction,
  className,
}: PageAIEmbedProps) {
  const navigate = useNavigate();
  const { suggestions, isLoading, dismiss, dismissAll, refresh } = usePageSuggestions({
    page,
    context,
  });

  const handleAction = (suggestion: PageSuggestion) => {
    switch (suggestion.actionType) {
      case 'navigate':
        navigate(suggestion.actionPayload);
        break;
      case 'chat':
        onChatAction?.(suggestion.actionPayload);
        break;
      case 'execute':
        onExecuteAction?.(suggestion.actionPayload);
        break;
    }
  };

  // 没有建议且不在加载中时不渲染
  if (!isLoading && suggestions.length === 0) {
    return null;
  }

  return (
    <div className={cn('w-full', className)}>
      <Card className="border-dashed border-primary/20 bg-primary/[0.02]">
        <CardHeader className="pb-3 pt-4 px-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary" />
              AI 洞察建议
            </CardTitle>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={refresh}
                aria-label="刷新建议"
              >
                <RefreshCw className="h-3 w-3" />
              </Button>
              {suggestions.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs text-muted-foreground"
                  onClick={dismissAll}
                >
                  全部忽略
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4 pt-0">
          {isLoading ? (
            <LoadingSkeleton />
          ) : (
            <div className="space-y-3">
              {suggestions.slice(0, 3).map((suggestion) => (
                <SuggestionCard
                  key={suggestion.id}
                  suggestion={suggestion}
                  onAction={handleAction}
                  onDismiss={dismiss}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default PageAIEmbed;
