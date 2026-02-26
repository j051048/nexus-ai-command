import React from 'react';
import { Progress } from '@/components/ui/progress';

interface ProgressItem {
  label: string;
  value: number;
  total?: number;
  color?: string;
}

interface ProgressTrackerProps {
  title?: string;
  items: ProgressItem[];
}

export default function ProgressTracker({ title, items = [] }: ProgressTrackerProps) {
  return (
    <div className="p-4 space-y-3">
      {title && <h3 className="text-sm font-semibold text-foreground">{title}</h3>}
      {items.map((item, i) => {
        const pct = item.total ? Math.round((item.value / item.total) * 100) : item.value;
        return (
          <div key={i} className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{item.label}</span>
              <span>{pct}%</span>
            </div>
            <Progress value={pct} className="h-2" />
          </div>
        );
      })}
    </div>
  );
}
