import type { LucideIcon } from 'lucide-react';
import {
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  FileCheck2,
  Search,
  TrendingUp,
  Users,
} from 'lucide-react';

interface Capability {
  id: string;
  title: string;
  prompt: string;
  icon: LucideIcon;
  category: string;
}

const CAPABILITIES: Capability[] = [
  {
    id: 'crm-brief',
    title: '客户概况',
    prompt: '帮我总结一下我目前负责的重点客户线索和最新进展',
    icon: Users,
    category: 'CRM',
  },
  {
    id: 'approval-list',
    title: '待我审核',
    prompt: '帮我列出目前所有需要我审批的申请，并按紧急程度排序',
    icon: FileCheck2,
    category: '审批',
  },
  {
    id: 'project-gantt',
    title: '项目进度',
    prompt: '分析一下目前所有进行中项目的整体进度，指出有风险的任务',
    icon: BriefcaseBusiness,
    category: '项目',
  },
  {
    id: 'leave-apply',
    title: '快速请假',
    prompt: '我下周三想请一天年假，帮我发起审批流程（请先检查我的余额）',
    icon: CalendarDays,
    category: 'OA',
  },
  {
    id: 'sales-forecast',
    title: '销售预测',
    prompt: '根据当前的销售漏斗数据，预测我本月的业绩目标达成情况',
    icon: TrendingUp,
    category: '销售',
  },
  {
    id: 'knowledge-search',
    title: '知识探索',
    prompt: '我想了解公司最新的加班补贴政策和报销流程',
    icon: Search,
    category: '知识库',
  },
];

interface CapabilityCardsProps {
  onSelect: (prompt: string) => void;
}

export function CapabilityCards({ onSelect }: CapabilityCardsProps) {
  return (
    <section className="mx-auto w-full max-w-2xl px-4 py-5">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-foreground">常用操作</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">选择一项，或直接输入任务</p>
        </div>
      </div>

      <div className="grid grid-cols-2 border-l border-t">
        {CAPABILITIES.map((capability) => {
          const Icon = capability.icon;
          return (
            <button
              key={capability.id}
              type="button"
              onClick={() => onSelect(capability.prompt)}
              className="group flex min-h-20 items-start gap-3 border-b border-r bg-card p-3 text-left transition-colors hover:bg-muted/60"
            >
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border bg-background text-muted-foreground">
                <Icon className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">
                  {capability.title}
                </span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {capability.category}
                </span>
              </span>
              <ArrowUpRight className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition-colors group-hover:text-foreground" />
            </button>
          );
        })}
      </div>
    </section>
  );
}
