import React, { useState } from 'react';
import { Sparkles, X, ChevronRight, Bot, ShieldAlert, Zap, BookOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from '@/components/ui/button';

interface Insight {
    type: 'risk' | 'summary' | 'suggestion';
    content: string;
}

interface AICopilotInsightProps {
    title: string;
    context: string;
    insights?: Insight[];
    className?: string;
}

export function AICopilotInsight({ title, context, insights, className }: AICopilotInsightProps) {
    const [isOpen, setIsOpen] = useState(false);

    // Default mock insights if none provided
    const displayInsights = insights || [
        { type: 'summary', content: '这是一份标准的企业文档，包含关键的合规条款。' },
        { type: 'suggestion', content: '建议核对第三条款中的交付日期是否与项目计划一致。' }
    ];

    return (
        <Popover open={isOpen} onOpenChange={setIsOpen}>
            <PopoverTrigger asChild>
                <button
                    className={cn(
                        "p-1.5 rounded-full transition-all hover:scale-110",
                        isOpen ? "bg-primary text-primary-foreground shadow-lg" : "bg-primary/10 text-primary hover:bg-primary/20",
                        className
                    )}
                    onClick={(e) => e.stopPropagation()}
                >
                    <Sparkles className="w-4 h-4" />
                </button>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-0 overflow-hidden border-primary/20 shadow-2xl animate-in zoom-in-95 duration-200" side="right" align="start">
                <div className="bg-gradient-to-r from-primary to-primary/80 px-4 py-3 text-white flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Bot className="w-4 h-4" />
                        <span className="text-sm font-bold">AI 深度洞察</span>
                    </div>
                    <button onClick={() => setIsOpen(false)}>
                        <X className="w-4 h-4 opacity-70 hover:opacity-100" />
                    </button>
                </div>

                <div className="p-4 space-y-4 bg-card">
                    <div>
                        <h4 className="text-xs font-bold text-muted-foreground uppercase mb-1">正在分析对象</h4>
                        <p className="text-sm font-medium text-foreground truncate">{title}</p>
                    </div>

                    <div className="space-y-3">
                        {displayInsights.map((insight, idx) => (
                            <div key={idx} className="flex gap-3 animate-in slide-in-from-left duration-300" style={{ animationDelay: `${idx * 150}ms` }}>
                                <div className={cn(
                                    "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm",
                                    insight.type === 'risk' ? "bg-destructive/10 text-destructive" :
                                        insight.type === 'suggestion' ? "bg-warning/10 text-warning" : "bg-success/10 text-success"
                                )}>
                                    {insight.type === 'risk' ? <ShieldAlert size={16} /> :
                                        insight.type === 'suggestion' ? <Zap size={16} /> : <BookOpen size={16} />}
                                </div>
                                <p className="text-xs leading-relaxed text-muted-foreground pt-1 italic">
                                    {insight.content}
                                </p>
                            </div>
                        ))}
                    </div>

                    <div className="pt-2 border-t border-border">
                        <Button variant="ghost" size="sm" className="w-full text-xs text-primary h-8 hover:bg-primary/5">
                            查看完整 AI 报告
                            <ChevronRight className="w-3 h-3 ml-1" />
                        </Button>
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    );
}
