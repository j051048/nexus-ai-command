import React, { useMemo } from 'react';
import { CalendarRange } from 'lucide-react';

interface ProjectTask {
  name: string;
  startDate: string;  // YYYY-MM-DD
  endDate: string;    // YYYY-MM-DD
  progress?: number;  // 0-100
  assignee?: string;
}

export interface GanttChartProps {
  title: string;
  projects?: ProjectTask[];
}

export default function GanttChart({ title, projects = [] }: GanttChartProps) {
  // Parse dates to find timeline boundaries
  const timeline = useMemo(() => {
    if (!projects || projects.length === 0) return null;

    let minTime = Infinity;
    let maxTime = -Infinity;

    const parsedProjects = projects.map(p => {
      const start = new Date(p.startDate).getTime();
      const end = new Date(p.endDate).getTime();
      if (!isNaN(start) && start < minTime) minTime = start;
      if (!isNaN(end) && end > maxTime) maxTime = end;
      return { ...p, start, end };
    });

    if (minTime === Infinity || maxTime === -Infinity || maxTime <= minTime) {
       // Fallback logic, give it 30 days gap if single day
       if (minTime !== Infinity) maxTime = minTime + 30 * 24 * 60 * 60 * 1000;
       else return null;
    }

    const totalDuration = maxTime - minTime;
    // Add 5% padding to left and right
    const paddedMin = minTime - totalDuration * 0.05;
    const paddedMax = maxTime + totalDuration * 0.05;
    const finalDuration = paddedMax - paddedMin;

    const formatDate = (timestamp: number) => {
      const d = new Date(timestamp);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    };

    return {
      min: paddedMin,
      max: paddedMax,
      duration: finalDuration,
      projects: parsedProjects,
      startDateLabel: formatDate(minTime),
      endDateLabel: formatDate(maxTime),
    };
  }, [projects]);

  if (!timeline) {
    return (
      <div className="p-4 border border-border rounded-xl text-center text-sm text-muted-foreground bg-card">
        缺少有效的排期数据
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border shadow-sm p-4 md:p-5 overflow-hidden">
      <div className="flex items-center gap-2 mb-6">
        <div className="p-1.5 bg-blue-500/10 rounded-md text-blue-500">
          <CalendarRange className="w-4 h-4" />
        </div>
        <h3 className="text-sm font-semibold text-foreground tracking-tight">{title}</h3>
      </div>

      <div className="relative">
        {/* Timeline Header Scale */}
        <div className="flex justify-between text-[10px] text-muted-foreground font-mono uppercase tracking-widest pl-[120px] mb-2 border-b border-border/50 pb-2 relative">
           <span>{timeline.startDateLabel}</span>
           <span className="absolute left-1/2 -translate-x-1/2">中期</span>
           <span>{timeline.endDateLabel}</span>
        </div>
        
        {/* Background vertical lines for visual scale */}
        <div className="absolute top-[30px] bottom-0 left-[120px] right-0 z-0 flex justify-between px-1">
           <div className="w-px h-full bg-border/40 dashed" />
           <div className="w-px h-full bg-border/40 dashed" />
           <div className="w-px h-full bg-border/40 dashed" />
        </div>

        {/* Tasks */}
        <div className="space-y-4 relative z-10 py-2">
          {timeline.projects.map((p, idx) => {
             const leftPercent = ((p.start - timeline.min) / timeline.duration) * 100;
             const widthPercent = ((p.end - p.start) / timeline.duration) * 100;
             const progress = p.progress || 0;
             
             return (
               <div key={idx} className="flex items-center group">
                 <div className="w-[120px] pr-3 flex-shrink-0">
                    <p className="text-xs font-medium text-foreground truncate" title={p.name}>{p.name}</p>
                    {p.assignee && <p className="text-[10px] text-muted-foreground truncate">{p.assignee}</p>}
                 </div>
                 
                 <div className="flex-1 relative h-6 rounded bg-muted/10 border border-border/30 hover:bg-muted/30 transition-colors">
                   <TooltipHover text={`${p.startDate} 至 ${p.endDate} (${progress}%)`}>
                     <div 
                       className="absolute top-1 bottom-1 rounded-sm overflow-hidden flex items-center shadow-sm cursor-help bg-blue-500/20 border border-blue-500/30"
                       style={{ left: `${Math.max(0, leftPercent)}%`, width: `${Math.max(2, widthPercent)}%` }}
                     >
                        <div 
                          className="h-full bg-blue-500 rounded-r-sm transition-all duration-1000"
                          style={{ width: `${progress}%` }}
                        />
                     </div>
                   </TooltipHover>
                 </div>
               </div>
             );
          })}
        </div>
      </div>
    </div>
  );
}

// Simple hover tooltip component
function TooltipHover({ children, text }: { children: React.ReactNode, text: string }) {
  return (
    <div className="relative group/tt w-full h-full">
      {children}
      <div className="absolute opacity-0 group-hover/tt:opacity-100 transition-opacity bottom-full left-1/2 -translate-x-1/2 mb-1 pointer-events-none bg-zinc-900 text-white text-[10px] px-2 py-1 rounded shadow-lg whitespace-nowrap z-50">
        {text}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-zinc-900" />
      </div>
    </div>
  );
}
