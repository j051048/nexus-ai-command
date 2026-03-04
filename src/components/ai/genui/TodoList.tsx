import React, { useState } from 'react';
import { Check, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TodoItem {
  label: string;
  done?: boolean;
  priority?: 'high' | 'medium' | 'low';
}

interface TodoListProps {
  title?: string;
  items: TodoItem[];
  interactive?: boolean;
}

const priorityColors = {
  high: 'text-red-600 dark:text-red-400',
  medium: 'text-amber-600 dark:text-amber-400',
  low: 'text-muted-foreground',
};

export function TodoList({ title, items, interactive = true }: TodoListProps) {
  const [checked, setChecked] = useState<Set<number>>(
    () => new Set(items.map((item, i) => item.done ? i : -1).filter(i => i >= 0))
  );

  if (!items || items.length === 0) return null;

  const toggle = (index: number) => {
    if (!interactive) return;
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const doneCount = checked.size;
  const total = items.length;

  return (
    <div className="p-4">
      {title && (
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold">{title}</h4>
          <span className="text-xs text-muted-foreground">{doneCount}/{total}</span>
        </div>
      )}
      {/* Progress bar */}
      <div className="h-1.5 bg-muted rounded-full mb-3 overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-300"
          style={{ width: `${total > 0 ? (doneCount / total) * 100 : 0}%` }}
        />
      </div>
      <ul className="space-y-1.5">
        {items.map((item, i) => {
          const isDone = checked.has(i);
          return (
            <li
              key={i}
              className={cn(
                'flex items-center gap-2.5 px-2.5 py-2.5 rounded-md text-sm transition-colors min-h-[44px]',
                interactive && 'cursor-pointer hover:bg-muted/50',
                isDone && 'opacity-60'
              )}
              onClick={() => toggle(i)}
            >
              {isDone ? (
                <Check className="w-4 h-4 text-primary shrink-0" />
              ) : (
                <Circle className={cn('w-4 h-4 shrink-0', item.priority ? priorityColors[item.priority] : 'text-muted-foreground')} />
              )}
              <span className={cn(isDone && 'line-through')}>{item.label}</span>
              {item.priority && !isDone && (
                <span className={cn('ml-auto text-[10px] uppercase font-medium', priorityColors[item.priority])}>
                  {item.priority}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default TodoList;
