import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface CalendarEvent {
  date: string; // YYYY-MM-DD format
  title: string;
  color?: string;
}

interface CalendarViewProps {
  year?: number;
  month?: number; // 1-12
  events?: CalendarEvent[];
  title?: string;
}

const DAY_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

const defaultEventColors = [
  'bg-blue-500',
  'bg-green-500',
  'bg-amber-500',
  'bg-red-500',
  'bg-violet-500',
  'bg-pink-500',
];

export default function CalendarView({ year, month, events, title }: CalendarViewProps) {
  const now = new Date();
  const displayYear = year || now.getFullYear();
  const displayMonth = month || now.getMonth() + 1; // 1-based

  const calendarData = useMemo(() => {
    const firstDay = new Date(displayYear, displayMonth - 1, 1);
    const lastDay = new Date(displayYear, displayMonth, 0);
    const daysInMonth = lastDay.getDate();
    const startDayOfWeek = firstDay.getDay(); // 0=Sunday

    // Build event map: date string -> events
    const eventMap = new Map<string, CalendarEvent[]>();
    if (events) {
      events.forEach((event) => {
        const existing = eventMap.get(event.date) || [];
        existing.push(event);
        eventMap.set(event.date, existing);
      });
    }

    // Build grid cells
    const cells: Array<{ day: number | null; date: string | null }> = [];

    // Empty cells before first day
    for (let i = 0; i < startDayOfWeek; i++) {
      cells.push({ day: null, date: null });
    }

    // Days of the month
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${displayYear}-${String(displayMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      cells.push({ day: d, date: dateStr });
    }

    // Fill remaining cells to complete last row
    const remainder = cells.length % 7;
    if (remainder > 0) {
      for (let i = 0; i < 7 - remainder; i++) {
        cells.push({ day: null, date: null });
      }
    }

    return { cells, eventMap, daysInMonth };
  }, [displayYear, displayMonth, events]);

  const { cells, eventMap } = calendarData;

  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  const monthNames = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月',
  ];

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-2">{title}</h4>}
      <div className="text-xs text-muted-foreground mb-3 font-medium">
        {displayYear}年 {monthNames[displayMonth - 1]}
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-0.5 mb-1">
        {DAY_LABELS.map((label) => (
          <div
            key={label}
            className="text-center text-[10px] font-medium text-muted-foreground py-1"
          >
            {label}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((cell, i) => {
          if (cell.day === null) {
            return <div key={i} className="h-10" />;
          }

          const dayEvents = cell.date ? eventMap.get(cell.date) || [] : [];
          const isToday = cell.date === todayStr;

          return (
            <div
              key={i}
              className={cn(
                'h-10 rounded-md flex flex-col items-center justify-start pt-1 relative',
                isToday && 'bg-blue-50 dark:bg-blue-950 ring-1 ring-blue-300 dark:ring-blue-700'
              )}
            >
              <span
                className={cn(
                  'text-xs tabular-nums',
                  isToday && 'font-bold text-blue-600 dark:text-blue-400'
                )}
              >
                {cell.day}
              </span>
              {dayEvents.length > 0 && (
                <div className="flex gap-0.5 mt-0.5">
                  {dayEvents.slice(0, 3).map((ev, j) => (
                    <div
                      key={j}
                      className={cn(
                        'w-1.5 h-1.5 rounded-full',
                        ev.color ? '' : defaultEventColors[j % defaultEventColors.length]
                      )}
                      style={ev.color ? { backgroundColor: ev.color } : undefined}
                      title={ev.title}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Event legend */}
      {events && events.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {events.slice(0, 6).map((ev, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <div
                className={cn(
                  'w-2 h-2 rounded-full flex-shrink-0',
                  ev.color ? '' : defaultEventColors[i % defaultEventColors.length]
                )}
                style={ev.color ? { backgroundColor: ev.color } : undefined}
              />
              <span className="truncate max-w-[100px]">{ev.title}</span>
            </div>
          ))}
          {events.length > 6 && (
            <span className="text-xs text-muted-foreground">
              +{events.length - 6} 更多
            </span>
          )}
        </div>
      )}
    </div>
  );
}
