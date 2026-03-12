import React, { useMemo } from 'react';
import { Activity } from 'lucide-react';

interface HeatmapData {
  date: string; // YYYY-MM-DD
  count: number;
}

export interface HeatmapProps {
  title: string;
  data: HeatmapData[];
}

export default function Heatmap({ title, data = [] }: HeatmapProps) {
  // We'll mimic a small 3-month (12 weeks) rolling heatmap if we have short data,
  // or just scale it up to the width of the container.
  const weeks = 12;
  const daysPerWeek = 7;
  
  const grid = useMemo(() => {
    // Generate an empty grid
    const g = Array.from({ length: daysPerWeek }, () => Array(weeks).fill(0));
    
    if (!data.length) return g;

    // Find max value to determine color intensity
    const maxVal = data.reduce((max, d) => Math.max(max, d.count), 1);
    
    // Sort chronologically and take last 84 days (12 weeks)
    const sorted = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    const recent = sorted.slice(-weeks * daysPerWeek);
    
    // Fill the grid sequentially from left to right, top to bottom 
    // (a real one aligns to actual weekdays, this is simplified for visual effect)
    let fillIndex = 0;
    for (let c = weeks - 1; c >= 0; c--) {
      for (let r = daysPerWeek - 1; r >= 0; r--) {
        if (fillIndex < recent.length) {
          const item = recent[recent.length - 1 - fillIndex];
          const intensity = Math.ceil((item.count / maxVal) * 4); // 0 to 4 levels
          g[r][c] = intensity;
          fillIndex++;
        }
      }
    }
    
    return g;
  }, [data]);

  const getColor = (level: number) => {
    switch (level) {
      case 4: return 'bg-emerald-500';
      case 3: return 'bg-emerald-500/80';
      case 2: return 'bg-emerald-500/50';
      case 1: return 'bg-emerald-500/20';
      default: return 'bg-muted/10 border-border/5';
    }
  };

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border shadow-sm p-4 md:p-5 overflow-hidden">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-4 h-4 text-emerald-500" />
        <h3 className="text-sm font-semibold text-foreground tracking-tight">{title}</h3>
      </div>

      <div className="w-full overflow-x-auto pb-2">
        <div className="flex gap-1.5 min-w-max">
          {Array.from({ length: weeks }).map((_, colIdx) => (
            <div key={colIdx} className="flex flex-col gap-1.5">
              {Array.from({ length: daysPerWeek }).map((_, rowIdx) => {
                const level = grid[rowIdx][colIdx];
                return (
                  <div
                    key={`${colIdx}-${rowIdx}`}
                    className={`w-4 h-4 md:w-5 md:h-5 rounded-sm border transition-colors hover:border-foreground/30 ${getColor(level)}`}
                    title={level > 0 ? `Activity Level: ${level}` : 'No activity'}
                  />
                );
              })}
            </div>
          ))}
        </div>
        
        <div className="flex justify-between items-center text-[10px] text-muted-foreground mt-3 px-1 font-mono uppercase tracking-widest">
           <span>Less</span>
           <div className="flex gap-1">
             <div className="w-3 h-3 rounded-sm border bg-muted/10" />
             <div className="w-3 h-3 rounded-sm border bg-emerald-500/20" />
             <div className="w-3 h-3 rounded-sm border bg-emerald-500/50" />
             <div className="w-3 h-3 rounded-sm border bg-emerald-500/80" />
             <div className="w-3 h-3 rounded-sm border bg-emerald-500" />
           </div>
           <span>More</span>
        </div>
      </div>
    </div>
  );
}
