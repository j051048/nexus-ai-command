import React, { useState } from 'react';
import { Bot, BookOpen, ChevronRight, ShieldAlert, Sparkles, X, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

interface Insight {
  type: 'risk' | 'summary' | 'suggestion';
  content: string;
}

interface AICopilotInsightProps {
  title: string;
  context: string;
  insights?: Insight[];
  className?: string;
  onViewReport?: () => void;
}

export function AICopilotInsight({ title, insights, className, onViewReport }: AICopilotInsightProps) {
  const [isOpen, setIsOpen] = useState(false);
  const displayInsights = insights || [];

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'rounded-full p-1.5 transition-all hover:scale-110',
            isOpen ? 'bg-primary text-primary-foreground shadow-lg' : 'bg-primary/10 text-primary hover:bg-primary/20',
            className,
          )}
          onClick={(event) => event.stopPropagation()}
        >
          <Sparkles className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 overflow-hidden border-primary/20 p-0 shadow-2xl animate-in zoom-in-95 duration-200" side="right" align="start">
        <div className="flex items-center justify-between bg-gradient-to-r from-primary to-primary/80 px-4 py-3 text-white">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            <span className="text-sm font-bold">智能洞察</span>
          </div>
          <button type="button" onClick={() => setIsOpen(false)}>
            <X className="h-4 w-4 opacity-70 hover:opacity-100" />
          </button>
        </div>

        <div className="space-y-4 bg-card p-4">
          <div>
            <h4 className="mb-1 text-xs font-bold uppercase text-muted-foreground">分析对象</h4>
            <p className="truncate text-sm font-medium text-foreground">{title}</p>
          </div>

          <div className="space-y-3">
            {displayInsights.length === 0 && (
              <p className="text-xs leading-relaxed text-muted-foreground">暂无真实洞察数据。</p>
            )}
            {displayInsights.map((insight, index) => (
              <div key={`${insight.type}-${index}`} className="flex gap-3 animate-in slide-in-from-left duration-300" style={{ animationDelay: `${index * 150}ms` }}>
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg shadow-sm',
                    insight.type === 'risk'
                      ? 'bg-destructive/10 text-destructive'
                      : insight.type === 'suggestion'
                        ? 'bg-warning/10 text-warning'
                        : 'bg-success/10 text-success',
                  )}
                >
                  {insight.type === 'risk' ? <ShieldAlert size={16} /> : insight.type === 'suggestion' ? <Zap size={16} /> : <BookOpen size={16} />}
                </div>
                <p className="pt-1 text-xs italic leading-relaxed text-muted-foreground">{insight.content}</p>
              </div>
            ))}
          </div>

          <div className="border-t border-border pt-2">
            <Button variant="ghost" size="sm" className="h-8 w-full text-xs text-primary hover:bg-primary/5" onClick={onViewReport}>
              查看完整报告
              <ChevronRight className="ml-1 h-3 w-3" />
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
