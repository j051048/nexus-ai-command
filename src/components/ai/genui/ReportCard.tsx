import React from 'react';
import { FileText, CalendarDays, Users, BarChart3, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ReportMetric {
  label: string;
  value: string | number;
  change?: number;
  unit?: string;
}

interface ReportSection {
  heading: string;
  items: string[];
}

interface ReportCardProps {
  title: string;
  type?: 'daily' | 'weekly' | 'meeting' | 'analysis';
  summary?: string;
  metrics?: ReportMetric[];
  sections?: ReportSection[];
}

const typeConfig = {
  daily: { icon: CalendarDays, label: '日报', accent: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-500/10' },
  weekly: { icon: BarChart3, label: '周报', accent: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-500/10' },
  meeting: { icon: Users, label: '会议纪要', accent: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10' },
  analysis: { icon: TrendingUp, label: '分析报告', accent: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-500/10' },
};

export function ReportCard({ title, type = 'daily', summary, metrics, sections }: ReportCardProps) {
  const config = typeConfig[type] || typeConfig.daily;
  const Icon = config.icon;

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={cn('rounded-lg p-2 shrink-0', config.bg)}>
          <Icon className={cn('w-5 h-5', config.accent)} />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold truncate">{title}</h4>
            <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded-full', config.bg, config.accent)}>
              {config.label}
            </span>
          </div>
          {summary && (
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{summary}</p>
          )}
        </div>
      </div>

      {/* Metrics row */}
      {metrics && metrics.length > 0 && (
        <div className={cn(
          'grid gap-2.5',
          metrics.length <= 2 && 'grid-cols-2',
          metrics.length === 3 && 'grid-cols-3',
          metrics.length >= 4 && 'grid-cols-2 sm:grid-cols-4',
        )}>
          {metrics.map((m, i) => (
            <div key={i} className="rounded-lg border bg-muted/30 px-3 py-2">
              <span className="text-[11px] text-muted-foreground">{m.label}</span>
              <div className="flex items-baseline gap-1 mt-0.5">
                <span className="text-lg font-bold tabular-nums">
                  {typeof m.value === 'number' ? m.value.toLocaleString() : m.value}
                </span>
                {m.unit && <span className="text-[11px] text-muted-foreground">{m.unit}</span>}
              </div>
              {m.change != null && (
                <div className={cn(
                  'flex items-center gap-0.5 text-[11px] font-medium mt-0.5',
                  m.change > 0 && 'text-green-600 dark:text-green-400',
                  m.change < 0 && 'text-red-600 dark:text-red-400',
                  m.change === 0 && 'text-muted-foreground',
                )}>
                  {m.change > 0 && <TrendingUp className="w-3 h-3" />}
                  {m.change < 0 && <TrendingDown className="w-3 h-3" />}
                  {m.change === 0 && <Minus className="w-3 h-3" />}
                  <span>{m.change > 0 ? '+' : ''}{m.change}%</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Content sections */}
      {sections && sections.length > 0 && (
        <div className="space-y-3">
          {sections.map((section, si) => (
            <div key={si}>
              <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                {section.heading}
              </h5>
              <ul className="space-y-1">
                {section.items.map((item, ii) => (
                  <li key={ii} className="flex items-start gap-2 text-sm leading-relaxed">
                    <FileText className="w-3.5 h-3.5 mt-0.5 shrink-0 text-muted-foreground/60" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ReportCard;
