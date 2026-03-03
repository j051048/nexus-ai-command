import React from 'react';
import { cn } from '@/lib/utils';

interface FunnelStage {
  label: string;
  value: number;
  color?: string;
}

interface FunnelChartProps {
  stages: FunnelStage[];
  title?: string;
}

const defaultColors = [
  'bg-blue-500',
  'bg-blue-400',
  'bg-cyan-500',
  'bg-cyan-400',
  'bg-teal-500',
  'bg-teal-400',
  'bg-emerald-500',
  'bg-emerald-400',
];

export default function FunnelChart({ stages, title }: FunnelChartProps) {
  if (!stages || stages.length === 0) return null;

  const maxValue = Math.max(...stages.map((s) => s.value));
  if (maxValue === 0) return null;

  return (
    <div className="p-4">
      {title && <h4 className="text-sm font-semibold mb-4">{title}</h4>}
      <div className="flex flex-col gap-2">
        {stages.map((stage, i) => {
          const widthPercent = (stage.value / maxValue) * 100;
          const prevValue = i > 0 ? stages[i - 1].value : null;
          const conversionRate =
            prevValue && prevValue > 0
              ? ((stage.value / prevValue) * 100).toFixed(1)
              : null;
          const barColor = stage.color
            ? undefined
            : defaultColors[i % defaultColors.length];

          return (
            <div key={i} className="flex flex-col items-center gap-1">
              {/* Stage row */}
              <div className="w-full flex items-center gap-3">
                {/* Label */}
                <div className="w-24 text-right flex-shrink-0">
                  <span className="text-xs font-medium text-muted-foreground truncate block">
                    {stage.label}
                  </span>
                </div>

                {/* Bar container */}
                <div className="flex-1 flex justify-center">
                  <div
                    className={cn(
                      'h-8 rounded-md flex items-center justify-center transition-all',
                      !stage.color && barColor
                    )}
                    style={{
                      width: `${Math.max(widthPercent, 8)}%`,
                      ...(stage.color ? { backgroundColor: stage.color } : {}),
                    }}
                  >
                    <span className="text-xs font-bold text-white drop-shadow-sm">
                      {stage.value.toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Percentage */}
                <div className="w-16 flex-shrink-0">
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {((stage.value / maxValue) * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Conversion rate between stages */}
              {conversionRate && (
                <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                  <span>转化率</span>
                  <span className={cn(
                    'font-medium',
                    parseFloat(conversionRate) >= 50
                      ? 'text-green-600 dark:text-green-400'
                      : parseFloat(conversionRate) >= 20
                      ? 'text-amber-600 dark:text-amber-400'
                      : 'text-red-600 dark:text-red-400'
                  )}>
                    {conversionRate}%
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
