import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCard {
  label: string;
  value: string | number;
  change?: number;
  unit?: string;
  trend?: 'up' | 'down' | 'flat';
}

interface StatCardsProps {
  title?: string;
  cards: StatCard[];
}

export function StatCards({ title, cards }: StatCardsProps) {
  if (!cards || cards.length === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className={cn(
        'grid gap-3',
        cards.length === 1 && 'grid-cols-1',
        cards.length === 2 && 'grid-cols-2',
        cards.length >= 3 && 'grid-cols-2 sm:grid-cols-3',
        cards.length >= 5 && 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4',
      )}>
        {cards.map((card, i) => {
          const trend = card.trend ?? (card.change != null ? (card.change > 0 ? 'up' : card.change < 0 ? 'down' : 'flat') : undefined);
          return (
            <div key={i} className="rounded-lg border bg-card p-3 flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{card.label}</span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-xl font-bold tabular-nums">
                  {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
                </span>
                {card.unit && <span className="text-xs text-muted-foreground">{card.unit}</span>}
              </div>
              {card.change != null && (
                <div className={cn(
                  'flex items-center gap-1 text-xs font-medium',
                  trend === 'up' && 'text-green-600 dark:text-green-400',
                  trend === 'down' && 'text-red-600 dark:text-red-400',
                  trend === 'flat' && 'text-muted-foreground',
                )}>
                  {trend === 'up' && <TrendingUp className="w-3 h-3" />}
                  {trend === 'down' && <TrendingDown className="w-3 h-3" />}
                  {trend === 'flat' && <Minus className="w-3 h-3" />}
                  <span>
                    {card.change > 0 ? '+' : ''}{card.change}%
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default StatCards;
