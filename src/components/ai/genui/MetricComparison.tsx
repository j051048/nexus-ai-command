import React from 'react';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';

interface MetricItem {
  label: string;
  current: number;
  previous: number;
  unit?: string;
}

interface MetricComparisonProps {
  title?: string;
  items: MetricItem[];
}

export default function MetricComparison({ title, items = [] }: MetricComparisonProps) {
  return (
    <div className="p-4 space-y-3">
      {title && <h3 className="text-sm font-semibold text-foreground">{title}</h3>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((item, i) => {
          const diff = item.current - item.previous;
          const pctChange = item.previous !== 0 ? Math.round((diff / item.previous) * 100) : 0;
          const isUp = diff > 0;
          const isFlat = diff === 0;

          return (
            <div key={i} className="rounded-lg border border-border p-3 space-y-1">
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div className="text-lg font-bold text-foreground">
                {item.current.toLocaleString()}{item.unit || ''}
              </div>
              <div className={`text-xs flex items-center gap-1 ${isUp ? 'text-green-600 dark:text-green-400' : isFlat ? 'text-muted-foreground' : 'text-red-600 dark:text-red-400'}`}>
                {isFlat ? <Minus className="w-3 h-3" /> : isUp ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                {pctChange >= 0 ? '+' : ''}{pctChange}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
