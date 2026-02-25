import React from 'react';
import { cn } from '@/lib/utils';

interface TimelineItem {
  time: string;
  title: string;
  description?: string;
  status?: 'done' | 'active' | 'pending';
}

interface TimelineProps {
  title?: string;
  items: TimelineItem[];
}

const statusConfig = {
  done: { dot: 'bg-primary', line: 'bg-primary', text: 'text-foreground' },
  active: { dot: 'bg-primary animate-pulse', line: 'bg-border', text: 'text-foreground font-medium' },
  pending: { dot: 'bg-muted-foreground/40', line: 'bg-border', text: 'text-muted-foreground' },
};

export function Timeline({ title, items }: TimelineProps) {
  if (!items || items.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className="relative">
        {items.map((item, i) => {
          const status = item.status ?? 'done';
          const config = statusConfig[status];
          const isLast = i === items.length - 1;

          return (
            <div key={i} className="flex gap-3 pb-4 last:pb-0">
              {/* Dot + Line */}
              <div className="flex flex-col items-center">
                <div className={cn('w-2.5 h-2.5 rounded-full mt-1.5 shrink-0', config.dot)} />
                {!isLast && (
                  <div className={cn('w-0.5 flex-1 mt-1', config.line)} />
                )}
              </div>
              {/* Content */}
              <div className="flex-1 min-w-0 pb-1">
                <div className="flex items-baseline gap-2">
                  <span className={cn('text-sm', config.text)}>{item.title}</span>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">{item.time}</span>
                </div>
                {item.description && (
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{item.description}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default Timeline;
