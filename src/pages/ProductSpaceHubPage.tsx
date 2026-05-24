import type { ComponentType, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Bot,
  Briefcase,
  Building2,
  ClipboardList,
  Database,
  FileCheck,
  FileSearch,
  FlaskConical,
  Landmark,
  LineChart,
  Network,
  Puzzle,
  Rocket,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Workflow,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface SpaceLink {
  title: string;
  description: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  tone: string;
}

interface ProductSpaceHubProps {
  eyebrow: string;
  title: string;
  description: string;
  primaryHref: string;
  primaryLabel: string;
  links: SpaceLink[];
  afterLinks?: ReactNode;
}

function ProductSpaceHub({
  eyebrow,
  title,
  description,
  primaryHref,
  primaryLabel,
  links,
  afterLinks,
}: ProductSpaceHubProps) {
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <section className="flex flex-col gap-4 border-b pb-6 md:flex-row md:items-end md:justify-between">
        <div className="max-w-2xl">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
            <Sparkles className="h-4 w-4" />
            {eyebrow}
          </div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        <Button asChild>
          <Link to={primaryHref}>{primaryLabel}</Link>
        </Button>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {links.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              to={item.href}
              className="group rounded-lg border bg-card p-4 shadow-sm transition-colors hover:bg-accent/40"
            >
              <div className="flex gap-3">
                <div
                  className={cn(
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                    item.tone,
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <h2 className="font-semibold leading-6 group-hover:text-primary">
                    {item.title}
                  </h2>
                  <p className="mt-1 text-sm leading-5 text-muted-foreground">
                    {item.description}
                  </p>
                </div>
              </div>
            </Link>
          );
        })}
      </section>

      {afterLinks}
    </main>
  );
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function IndustryExpertPanel() {
  const prompts = [
    '帮我对标 Thermo Fisher 的同类产品，生成一份科学仪器竞品战卡。',
    '根据招标文件评分标准，评估我们的技术方案可能得分和短板。',
    '这个高校实验室客户通常的采购决策链是什么？请给出跟进节奏。',
  ];

  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-600">
            <FlaskConical className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold text-primary">科学仪器行业专家</div>
            <h2 className="mt-1 text-lg font-semibold">把行业知识变成销售动作</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
              预置竞品对比、招投标评分、科研客户决策链和技术拜访准备模板。销售无需从空白聊天开始，直接让 AI 进入行业语境。
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={() =>
            triggerAI('请进入科学仪器行业专家模式，先根据我的客户和产品线提出 5 个最值得补齐的行业知识库条目。')
          }
        >
          <Sparkles className="mr-2 h-4 w-4" />
          生成知识库缺口
        </Button>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => triggerAI(prompt)}
            className="rounded-lg border bg-background/60 p-3 text-left text-sm leading-6 transition-colors hover:bg-accent"
          >
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}

export function WorkspaceHubPage() {
  return (
    <ProductSpaceHub
      eyebrow="工作台"
      title="把日常运营收进一个空间"
      description="项目、审批、合同、OA、人事、财务和流程都放在这里。默认导航不再堆满入口，但高频业务仍然可以一步进入。"
      primaryHref="/projects"
      primaryLabel="进入项目"
      links={[
        {
          title: '项目管理',
          description: '查看交付进度、负责人和阶段状态。',
          href: '/projects',
          icon: Briefcase,
          tone: 'bg-blue-500/10 text-blue-600',
        },
        {
          title: '审批中心',
          description: '处理报销、请假、合同和流程审批。',
          href: '/approval',
          icon: FileCheck,
          tone: 'bg-emerald-500/10 text-emerald-600',
        },
        {
          title: '合同管理',
          description: '管理合同台账、回款节点和客户关联。',
          href: '/contracts',
          icon: FileSearch,
          tone: 'bg-amber-500/10 text-amber-600',
        },
        {
          title: 'OA 办公',
          description: '公告、考勤和协同事务入口。',
          href: '/oa',
          icon: ClipboardList,
          tone: 'bg-sky-500/10 text-sky-600',
        },
        {
          title: 'HR 中心',
          description: '员工、组织、绩效和入职流程。',
          href: '/hr',
          icon: Users,
          tone: 'bg-rose-500/10 text-rose-600',
        },
        {
          title: '财务中心',
          description: '费用、预算、回款和财务审批。',
          href: '/finance',
          icon: Landmark,
          tone: 'bg-lime-500/10 text-lime-700',
        },
        {
          title: '工作流',
          description: '流程列表、模板和表单设计。',
          href: '/workflows',
          icon: Workflow,
          tone: 'bg-violet-500/10 text-violet-600',
        },
        {
          title: '组织架构',
          description: '团队、部门和权限上下文。',
          href: '/org-chart',
          icon: Network,
          tone: 'bg-slate-500/10 text-slate-600',
        },
      ]}
      afterLinks={<IndustryExpertPanel />}
    />
  );
}

export function DataHubPage() {
  return (
    <ProductSpaceHub
      eyebrow="数据"
      title="看趋势，而不是翻模块"
      description="报表、目标、ROI、客户成功和经营总览集中在数据空间。它承接旧 Dashboard 的分析职责，但不再抢占首页。"
      primaryHref="/reports"
      primaryLabel="查看报表"
      links={[
        {
          title: '行动台运营分析',
          description: '跟踪采纳率、完成率、忽略率和高风险未闭环行动。',
          href: '/action-analytics',
          icon: Activity,
          tone: 'bg-rose-500/10 text-rose-600',
        },
        {
          title: '报表中心',
          description: '查看业务报表和关键经营指标。',
          href: '/reports',
          icon: BarChart3,
          tone: 'bg-blue-500/10 text-blue-600',
        },
        {
          title: '目标看板',
          description: '跟踪销售目标、团队进度和差距。',
          href: '/target-dashboard',
          icon: Target,
          tone: 'bg-orange-500/10 text-orange-600',
        },
        {
          title: 'AI 报表引擎',
          description: '用自然语言生成分析和图表。',
          href: '/report-builder',
          icon: Sparkles,
          tone: 'bg-violet-500/10 text-violet-600',
        },
        {
          title: '战绩看板',
          description: '保留原员工战绩、奖金和排行榜视图。',
          href: '/performance-dashboard',
          icon: LineChart,
          tone: 'bg-emerald-500/10 text-emerald-600',
        },
        {
          title: '客户成功',
          description: '跟踪活跃、价值、续约和验收风险。',
          href: '/customer-success',
          icon: Building2,
          tone: 'bg-cyan-500/10 text-cyan-600',
        },
        {
          title: '经营总览',
          description: '面向管理层的经营和组织概览。',
          href: '/boss-dashboard',
          icon: Database,
          tone: 'bg-slate-500/10 text-slate-600',
        },
      ]}
    />
  );
}

export function AICenterPage() {
  return (
    <ProductSpaceHub
      eyebrow="AI 中心"
      title="把 Agent、知识和治理放在一起"
      description="AI 中心承载知识库、VMD、插件、模型和工具治理。聊天仍然随处可用，但配置和治理集中管理。"
      primaryHref="/knowledge"
      primaryLabel="打开知识库"
      links={[
        {
          title: '知识库',
          description: '管理行业知识、文档检索和组织记忆。',
          href: '/knowledge',
          icon: Database,
          tone: 'bg-blue-500/10 text-blue-600',
        },
        {
          title: 'VMD 虚拟市场部',
          description: '管理营销 Agent、线索和内容任务。',
          href: '/vmd',
          icon: Rocket,
          tone: 'bg-rose-500/10 text-rose-600',
        },
        {
          title: '插件市场',
          description: '安装和管理扩展能力。',
          href: '/plugins',
          icon: Puzzle,
          tone: 'bg-amber-500/10 text-amber-600',
        },
        {
          title: '模型管理',
          description: '配置模型、供应商和调用策略。',
          href: '/llm/models',
          icon: Settings,
          tone: 'bg-slate-500/10 text-slate-600',
        },
        {
          title: 'Tool 治理',
          description: '审计工具风险、权限和 RAG 召回质量。',
          href: '/tools/governance',
          icon: ShieldCheck,
          tone: 'bg-emerald-500/10 text-emerald-600',
        },
        {
          title: 'Agent Runs',
          description: '查看 Agent 运行、回放和质量趋势。',
          href: '/agent-runs',
          icon: Bot,
          tone: 'bg-violet-500/10 text-violet-600',
        },
      ]}
    />
  );
}
