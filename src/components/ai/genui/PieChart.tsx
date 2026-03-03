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
  '#3b82f6', // blue-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#ef4444', // red-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
  '#14b8a6', // teal-500
  '#6366f1', // indigo-500
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
    <div className="p-4">
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
