import { AlertTriangle, CheckSquare2, FileStack, Scale } from 'lucide-react';

import { cn } from '@/lib/utils';

interface TenderReportSection {
  id: string;
  title: string;
  content: string;
  tone: 'danger' | 'warning' | 'neutral' | 'action';
  defaultOpen?: boolean;
}

function stripMarkdownTitle(line: string) {
  return line.replace(/^#{1,6}\s*/, '').trim();
}

export function buildTenderReportSections(report: string): TenderReportSection[] {
  const chunks = report
    .split(/\n(?=#{3,6}\s)/g)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk, index) => {
      const [firstLine, ...rest] = chunk.split('\n');
      return {
        id: `source-${index}`,
        title: stripMarkdownTitle(firstLine || `分析段落 ${index + 1}`),
        content: rest.join('\n').trim() || chunk,
      };
    });

  const used = new Set<number>();
  const pick = (id: string, title: string, tone: TenderReportSection['tone'], pattern: RegExp) => {
    const matches = chunks
      .map((section, index) => ({ section, index }))
      .filter(({ section }) => pattern.test(section.title) || pattern.test(section.content));
    matches.forEach(({ index }) => used.add(index));
    return {
      id,
      title,
      tone,
      content: matches.map(({ section }) => `### ${section.title}\n${section.content}`).join('\n\n') || '暂未发现明确内容，仍需人工复核原文件。',
    } satisfies TenderReportSection;
  };

  const sections = [
    pick('redlines', '否决项与资格风险', 'danger', /否决|redline|废标|资格|必须|不得/i),
    pick('deviations', '扣分与技术偏离', 'warning', /扣分|偏离|deviation|风险|评分|响应/i),
    pick('materials', '待补材料与证据', 'neutral', /材料|证明|附件|资质|补齐|证据|文件/i),
  ];
  const remaining = chunks.filter((_, index) => !used.has(index));
  sections.push({
    id: 'evidence',
    title: '完整分析依据',
    tone: 'action',
    content: remaining.map((section) => `### ${section.title}\n${section.content}`).join('\n\n') || report,
  });
  return sections;
}

const TONE_STYLES = {
  danger: { icon: AlertTriangle, className: 'border-l-destructive', iconClass: 'text-destructive' },
  warning: { icon: Scale, className: 'border-l-amber-500', iconClass: 'text-amber-600' },
  neutral: { icon: FileStack, className: 'border-l-sky-500', iconClass: 'text-sky-600' },
  action: { icon: CheckSquare2, className: 'border-l-primary', iconClass: 'text-primary' },
};

export function TenderReportSections({ report }: { report: string }) {
  return (
    <div className="space-y-2">
      {buildTenderReportSections(report).map((section, index) => {
        const style = TONE_STYLES[section.tone];
        const Icon = style.icon;
        return (
          <details
            key={section.id}
            open={index === 0}
            className={cn('group border border-l-2 bg-background', style.className)}
          >
            <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium">
              <Icon className={cn('h-4 w-4', style.iconClass)} />
              <span>{section.title}</span>
              <span className="ml-auto text-xs font-normal text-muted-foreground group-open:hidden">展开</span>
              <span className="ml-auto hidden text-xs font-normal text-muted-foreground group-open:inline">收起</span>
            </summary>
            <pre className="whitespace-pre-wrap border-t px-4 py-3 font-sans text-sm leading-6 text-foreground">
              {section.content}
            </pre>
          </details>
        );
      })}
    </div>
  );
}
