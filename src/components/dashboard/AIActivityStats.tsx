import React from 'react';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  MessageSquare,
  Zap,
  Target,
} from 'lucide-react';

interface AIActivityStatsProps {
  stats: {
    totalConversations: number;
    tasksHandled: number;
    avgConfidence: number;
    responseTime: string;
  };
  className?: string;
}

const STAT_ITEMS = [
  {
    key: 'totalConversations',
    label: '活跃对话',
    icon: MessageSquare,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
    suffix: '',
  },
  {
    key: 'tasksHandled',
    label: '任务达成',
    icon: Target,
    color: 'text-purple-500',
    bg: 'bg-purple-500/10',
    suffix: '',
  },
  {
    key: 'avgConfidence',
    label: 'AI 置信度',
    icon: Zap,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
    suffix: '%',
  },
  {
    key: 'responseTime',
    label: '响应速度',
    icon: TrendingUp,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    suffix: '',
  },
];

export const AIActivityStats = React.memo(function AIActivityStats({
  stats,
  className,
}: AIActivityStatsProps) {
  return (
    <div className={cn("grid grid-cols-2 lg:grid-cols-4 gap-4", className)}>
      {STAT_ITEMS.map((item) => {
        const Icon = item.icon;
        const value = stats[item.key as keyof typeof stats];

        return (
          <div
            key={item.key}
            className="bento-card glass-premium p-5 rounded-3xl border-white/5 relative overflow-hidden group hover:scale-[1.02] transition-all duration-500"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            
            <div className="flex items-start justify-between relative z-10 mb-4">
              <div className={cn("p-2.5 rounded-2xl", item.bg)}>
                <Icon className={cn("w-5 h-5", item.color)} />
              </div>
              <div className="h-10 w-24 opacity-20 pointer-events-none">
                <svg className="w-full h-full" viewBox="0 0 100 40">
                  <path
                    d="M0 35 Q 25 35, 50 15 T 100 5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className={item.color}
                  />
                </svg>
              </div>
            </div>

            <div className="relative z-10">
              <p className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-widest mb-1.5">{item.label}</p>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-numbers font-black tracking-tighter transition-all group-hover:tracking-normal">
                  {value}
                </span>
                {item.suffix && (
                  <span className="text-xs font-bold text-muted-foreground/40">{item.suffix}</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
});
