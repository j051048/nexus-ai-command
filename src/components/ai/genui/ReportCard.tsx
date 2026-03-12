import React from 'react';
import { FileText, Calendar, CheckCircle2, Clock, ChevronRight } from 'lucide-react';

interface ReportSection {
  heading: string;
  items: string[];
}

export interface ReportCardProps {
  title: string;
  type?: 'daily' | 'weekly' | 'monthly' | 'custom' | 'meeting' | 'analysis';
  summary?: string;
  metrics?: { label: string; value: string | number; change?: number }[];
  sections?: ReportSection[];
}

export default function ReportCard({ title, type = 'daily', summary, metrics, sections = [] }: ReportCardProps) {
  const getIcon = (heading: string) => {
    if (heading.includes('完成') || heading.includes('已做') || heading.includes('总结')) 
      return <CheckCircle2 className="w-4 h-4 text-green-500" />;
    if (heading.includes('进行') || heading.includes('当前') || heading.includes('进度')) 
      return <Clock className="w-4 h-4 text-blue-500" />;
    if (heading.includes('计划') || heading.includes('下期') || heading.includes('明日')) 
      return <Calendar className="w-4 h-4 text-orange-500" />;
    return <ChevronRight className="w-4 h-4 text-primary" />;
  };

  return (
    <div className="flex flex-col w-full text-left">
      <div className="bg-primary/5 border-b border-border/50 px-5 py-4 flex items-start gap-3">
        <div className="p-2 bg-primary/10 rounded-lg text-primary mt-0.5">
          <FileText className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            {title}
            {type && (
              <span className="text-[10px] uppercase tracking-wider font-semibold bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                {type}
              </span>
            )}
          </h3>
          {summary && (
            <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
              {summary}
            </p>
          )}
        </div>
      </div>

      {metrics && metrics.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 px-5 py-4 bg-muted/20 border-b border-border/50">
          {metrics.map((m, i) => (
            <div key={i} className="flex flex-col gap-1">
              <span className="text-xs font-medium text-muted-foreground">{m.label}</span>
              <div className="flex items-baseline gap-2">
                <span className="text-lg font-bold text-foreground">{m.value}</span>
                {m.change !== undefined && (
                  <span className={`text-[10px] font-medium ${m.change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {m.change >= 0 ? '+' : ''}{m.change}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="px-5 py-5 space-y-6">
        {sections && sections.length > 0 ? (
          sections.map((section, idx) => (
            <div key={idx} className="space-y-3">
              <h4 className="text-sm font-medium text-foreground flex items-center gap-1.5 border-l-2 border-primary/50 pl-2">
                {getIcon(section.heading)}
                {section.heading}
              </h4>
              {section.items && section.items.length > 0 ? (
                <ul className="space-y-2 pl-4">
                  {section.items.map((item, itemIdx) => (
                    <li key={itemIdx} className="text-sm text-foreground/80 leading-relaxed list-disc list-outside marker:text-muted-foreground/60">
                      {item}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground italic pl-4">无相关记录</p>
              )}
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">报告内容为空</p>
        )}
      </div>
    </div>
  );
}
