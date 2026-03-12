import React from 'react';
import { Map, MapPin } from 'lucide-react';

interface GeoData {
  region: string;
  value: number;
  percentage?: number;
}

export interface GeoChartProps {
  title: string;
  data: GeoData[];
  valueLabel?: string;
}

export default function GeoChart({ title, data = [], valueLabel = '数值' }: GeoChartProps) {
  // Calculate max value for relative bar sizing
  const maxValue = data.reduce((max, d) => Math.max(max, d.value), 0);
  
  // Sort from highest to lowest
  const sortedData = [...data].sort((a, b) => b.value - a.value);

  return (
    <div className="flex flex-col w-full bg-card rounded-xl border border-border shadow-sm p-4 md:p-5">
      <div className="flex items-center gap-2 mb-5">
        <div className="p-1.5 bg-primary/10 rounded-md text-primary">
          <Map className="w-4 h-4" />
        </div>
        <h3 className="text-sm font-semibold text-foreground tracking-tight">{title}</h3>
      </div>

      <div className="space-y-4 relative">
        {/* Background vertical grid line */}
        <div className="absolute top-0 bottom-0 left-[30%] border-l border-border/50 border-dashed -z-10" />

        {sortedData.map((item, idx) => {
          const widthPercent = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
          return (
            <div key={idx} className="flex items-center gap-3">
              <div className="w-[30%] flex justify-end items-center gap-1.5 pr-3">
                <span className="text-sm font-medium text-foreground truncate">{item.region}</span>
                <MapPin className="w-3 h-3 text-muted-foreground/50 hidden sm:block" />
              </div>
              <div className="w-[70%] flex items-center gap-3">
                <div className="flex-1 h-3 md:h-4 bg-muted/30 rounded-full overflow-hidden flex shadow-inner">
                  <div 
                    className={`h-full rounded-r-full flex items-center justify-end px-1 transition-all duration-1000 ease-out
                      ${idx === 0 ? 'bg-primary' : idx < 3 ? 'bg-primary/80' : 'bg-primary/50'}
                    `}
                    style={{ width: `${widthPercent}%` }}
                  />
                </div>
                <div className="w-16 flex-shrink-0 flex items-baseline gap-1">
                  <span className="text-sm font-mono font-bold">{item.value.toLocaleString()}</span>
                  {item.percentage !== undefined && (
                    <span className="text-[10px] text-muted-foreground font-mono">{item.percentage}%</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      
      <div className="mt-5 pt-3 border-t border-border flex justify-between font-mono text-[10px] text-muted-foreground uppercase tracking-widest">
        <span>0</span>
        <span>Top Region: {sortedData.length > 0 ? sortedData[0].region : '-'}</span>
        <span>{maxValue.toLocaleString()} {valueLabel}</span>
      </div>
    </div>
  );
}
