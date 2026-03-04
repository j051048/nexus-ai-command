import React from 'react';
import { cn } from '@/lib/utils';

interface PieSlice {
  label: string;
  value: number;
  color?: string;
}

interface PieChartProps {
  data: PieSlice[];
  title?: string;
  donut?: boolean;
}

const defaultColors = [
  'hsl(var(--primary))',
  'hsl(var(--chart-2, 220 70% 55%))',
  'hsl(var(--chart-3, 150 60% 45%))',
  'hsl(var(--chart-4, 30 80% 55%))',
  'hsl(var(--chart-5, 280 65% 55%))',
  'hsl(var(--chart-6, 260 50% 68%))',
  'hsl(var(--chart-7, 140 55% 62%))',
  'hsl(var(--chart-8, 45 85% 60%))',
  'hsl(var(--chart-9, 170 50% 50%))',
  'hsl(var(--chart-10, 240 60% 60%))',
];

export default function PieChart({ data, title, donut = false }: PieChartProps) {
  if (!data || data.length === 0) return null;

  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) return null;

  // Build conic-gradient stops
  let accumulated = 0;
  const gradientStops = data
    .map((slice, i) => {
      const color = slice.color || defaultColors[i % defaultColors.length];
      const start = accumulated;
      const end = accumulated + (slice.value / total) * 360;
      accumulated = end;
      return `${color} ${start}deg ${end}deg`;
    })
    .join(', ');

  const gradientStyle: React.CSSProperties = {
    background: `conic-gradient(${gradientStops})`,
  };

  return (
    <div className="p-4 min-h-[180px]">
      {title && <h4 className="text-sm font-semibold mb-3">{title}</h4>}
      <div className="flex flex-col sm:flex-row items-center gap-4">
        {/* Chart */}
        <div className="relative flex-shrink-0">
          <div
            className="w-32 h-32 rounded-full"
            style={gradientStyle}
          />
          {donut && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-background" />
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-1.5">
          {data.map((slice, i) => {
            const color = slice.color || defaultColors[i % defaultColors.length];
            const percentage = total > 0 ? ((slice.value / total) * 100).toFixed(1) : '0';
            return (
              <div key={i} className="flex items-center gap-2 text-sm">
                <div
                  className="w-3 h-3 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="text-muted-foreground truncate max-w-[140px]">
                  {slice.label}
                </span>
                <span className="font-medium tabular-nums ml-auto">{percentage}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
