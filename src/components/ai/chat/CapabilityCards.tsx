import React from 'react';
import { 
  Users, 
  FileCheck, 
  Briefcase, 
  Calendar, 
  TrendingUp, 
  Search, 
  Sparkles,
  ArrowRight
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Capability {
  id: string;
  title: string;
  description: string;
  prompt: string;
  icon: React.ReactNode;
  color: string;
  category: string;
}

const CAPABILITIES: Capability[] = [
  {
    id: 'crm-brief',
    title: '客户概况',
    description: '查看我负责的重点线索和进展',
    prompt: '帮我总结一下我目前负责的重点客户线索和最新进展',
    icon: <Users className="w-5 h-5" />,
    color: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
    category: 'CRM',
  },
  {
    id: 'approval-list',
    title: '待我审核',
    description: '快速列出所有需要我审批的申请',
    prompt: '帮我列出目前所有需要我审批的申请，并按紧急程度排序',
    icon: <FileCheck className="w-5 h-5" />,
    color: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    category: '审批',
  },
  {
    id: 'project-gantt',
    title: '项目进度',
    description: '分析当前各项目的风险和里程碑',
    prompt: '分析一下目前所有进行中项目的整体进度，指出有风险的任务',
    icon: <Briefcase className="w-5 h-5" />,
    color: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
    category: '项目',
  },
  {
    id: 'leave-apply',
    title: '快速请假',
    description: '基于日历自动安排请假流程',
    prompt: '我下周三想请一天年假，帮我发起审批流程（请先检查我的余额）',
    icon: <Calendar className="w-5 h-5" />,
    color: 'bg-green-500/10 text-green-500 border-green-500/20',
    category: 'OA',
  },
  {
    id: 'sales-forecast',
    title: '销售预测',
    description: '基于漏斗数据预测本月目标达成',
    prompt: '根据当前的销售漏斗数据，预测我本月的业绩目标达成情况',
    icon: <TrendingUp className="w-5 h-5" />,
    color: 'bg-rose-500/10 text-rose-500 border-rose-500/20',
    category: '销售',
  },
  {
    id: 'knowledge-search',
    title: '知识探索',
    description: '全文搜索公司制度或技术文档',
    prompt: '我想了解公司最新的加班补贴政策和报销流程',
    icon: <Search className="w-5 h-5" />,
    color: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20',
    category: '知识库',
  },
];

interface CapabilityCardsProps {
  onSelect: (prompt: string) => void;
}

export function CapabilityCards({ onSelect }: CapabilityCardsProps) {
  return (
    <div className="w-full max-w-4xl mx-auto p-4 space-y-6">
      <div className="flex items-center gap-2 px-2">
        <Sparkles className="w-5 h-5 text-primary animate-pulse" />
        <h3 className="text-lg font-bold tracking-tight text-foreground/80">你可以尝试这样对我命令:</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {CAPABILITIES.map((cap) => (
          <button
            key={cap.id}
            onClick={() => onSelect(cap.prompt)}
            className={cn(
              "group relative flex flex-col items-start p-5 rounded-2xl border transition-all duration-300 text-left",
              "bg-secondary/20 hover:bg-secondary/40 hover:border-primary/30 hover:shadow-xl hover:-translate-y-1 active:scale-95",
              cap.color
            )}
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="p-2 rounded-xl bg-background/50 shadow-sm">
                {cap.icon}
              </div>
              <span className="text-[10px] font-bold uppercase tracking-widest opacity-60">
                {cap.category}
              </span>
            </div>
            
            <h4 className="font-bold text-base mb-1 text-foreground">
              {cap.title}
            </h4>
            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
              {cap.description}
            </p>

            <div className="mt-4 flex items-center gap-1.5 text-[10px] font-bold text-primary opacity-0 group-hover:opacity-100 transition-opacity translate-x-[-10px] group-hover:translate-x-0 group-transition uppercase">
              立即尝试 <ArrowRight className="w-3 h-3" />
            </div>

            {/* Decorative radial gradient */}
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity" />
          </button>
        ))}
      </div>
    </div>
  );
}
