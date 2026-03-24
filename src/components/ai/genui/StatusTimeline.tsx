import React from 'react';
import { cn } from '@/lib/utils';

interface TimelineEvent {
  time: string;
  title: string;
  description?: string;
  status?: 'success' | 'warning' | 'error' | 'info';
}

interface StatusTimelineProps {
  events: TimelineEvent[];
  title?: string;
}

const statusColors = {
  success: {
    dot: 'bg-green-500 dark:bg-green-400',
    ring: 'ring-green-100 dark:ring-green-900',
    text: 'text-green-700 dark:text-green-300',
  },
  warning: {
    dot: 'bg-amber-500 dark:bg-amber-400',
    ring: 'ring-amber-100 dark:ring-amber-900',
    text: 'text-amber-700 dark:text-amber-300',
  },
  error: {
    dot: 'bg-red-500 dark:bg-red-400',
    ring: 'ring-red-100 dark:ring-red-900',
    text: 'text-red-700 dark:text-red-300',
  },
  info: {
    dot: 'bg-blue-500 dark:bg-blue-400',
    ring: 'ring-blue-100 dark:ring-blue-900',
    text: 'text-blue-700 dark:text-blue-300',
  },
};

export default function StatusTimeline({ events, title }: StatusTimelineProps) {
  if (!events || events.length === 0) return null;

  // 过滤掉截断的 JSON 导致的不完整 event 对象
  const validEvents = events.filter(
    (e) => e && typeof e === 'object' && typeof e.title === 'string'
  );
  if (validEvents.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-4">{title}</h4>}
      <div className="relative">
        {validEvents.map((event, i) => {
          const status = event.status || 'info';
          const colors = statusColors[status];
          const isLast = i === validEvents.length - 1;

          return (
            <div key={i} className="flex gap-3 pb-4 last:pb-0">
              {/* Timeline column */}
              <div className="flex flex-col items-center flex-shrink-0">
                <div
                  className={cn(
                    'w-3 h-3 rounded-full ring-4 flex-shrink-0',
                    colors.dot,
                    colors.ring
                  )}
                />
                {!isLast && (
                  <div className="w-0.5 flex-1 bg-border min-h-[16px]" />
                )}
              </div>

              {/* Content */}
              <div className="pb-2 min-w-0 -mt-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium">{event.title}</p>
                  <span className="text-xs text-muted-foreground">{event.time}</span>
                </div>
                {event.description && (
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                    {event.description}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
