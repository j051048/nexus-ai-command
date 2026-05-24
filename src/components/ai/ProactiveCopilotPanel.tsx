import { useMemo, type ComponentType } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  FileCheck,
  Sparkles,
  Users,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useInboxActions, type InboxActionItem } from '@/hooks/useInboxActions';
import { cn } from '@/lib/utils';

interface CopilotInsight {
  id: string;
  title: string;
  description: string;
  prompt: string;
  href?: string;
  icon: ComponentType<{ className?: string }>;
  tone: string;
}

function sourceLabel(item: InboxActionItem) {
  if (item.source === 'approval') return '审批';
  if (item.source === 'crm') return '客户';
  if (item.source === 'notification') return '通知';
  return '系统';
}

function buildActionInsights(items: InboxActionItem[]): CopilotInsight[] {
  return items.slice(0, 3).map((item) => ({
    id: item.id,
    title: `${sourceLabel(item)}：${item.title}`,
    description: item.reason || item.description || '这是一条需要处理的行动项。',
    prompt: `请帮我分析这个行动项并给出下一步建议：${item.title}`,
    href: item.action_url || item.actions.find((action) => action.navigate_to)?.navigate_to || undefined,
    icon: item.source === 'approval' ? FileCheck : item.source === 'crm' ? Users : AlertTriangle,
    tone:
      item.priority === 'urgent'
        ? 'bg-destructive/10 text-destructive'
        : item.priority === 'high'
          ? 'bg-orange-500/10 text-orange-600'
          : 'bg-primary/10 text-primary',
  }));
}

function routeInsights(pathname: string): CopilotInsight[] {
  if (pathname.startsWith('/crm')) {
    return [
      {
        id: 'crm-risk',
        title: '客户健康巡检',
        description: '找出 30 天未跟进、高价值但停滞、阶段推进异常的客户。',
        prompt: '请基于当前 CRM 页面，列出最需要优先跟进的客户，并说明原因和建议动作。',
        href: '/crm',
        icon: Users,
        tone: 'bg-amber-500/10 text-amber-600',
      },
      {
        id: 'crm-brief',
        title: '生成销售晨会摘要',
        description: '把新增客户、重点机会和风险客户整理成可直接开会使用的摘要。',
        prompt: '请生成今天 CRM 销售晨会摘要，包含新增客户、重点机会、风险客户和建议动作。',
        icon: BarChart3,
        tone: 'bg-blue-500/10 text-blue-600',
      },
    ];
  }

  if (pathname.startsWith('/approval')) {
    return [
      {
        id: 'approval-risk',
        title: '审批风险预审',
        description: '优先检查金额异常、超时和缺少说明的审批项。',
        prompt: '请帮我检查待审批事项中的风险点，并按紧急程度排序。',
        href: '/approval',
        icon: FileCheck,
        tone: 'bg-emerald-500/10 text-emerald-600',
      },
    ];
  }

  if (pathname.startsWith('/data') || pathname.includes('dashboard') || pathname.startsWith('/reports')) {
    return [
      {
        id: 'data-gap',
        title: '经营差距解读',
        description: '把目标、达成率和风险指标整理成一页管理层摘要。',
        prompt: '请分析当前数据空间里的经营差距，给出本周最该关注的 3 个指标。',
        href: '/reports',
        icon: BarChart3,
        tone: 'bg-blue-500/10 text-blue-600',
      },
    ];
  }

  return [
    {
      id: 'daily-plan',
      title: '整理今天的优先级',
      description: '根据待办、客户和审批，帮你排出今天最该先处理的事项。',
      prompt: '请帮我整理今天的工作优先级，按影响和紧急程度排序。',
      href: '/dashboard',
      icon: CheckCircle2,
      tone: 'bg-primary/10 text-primary',
    },
  ];
}

export function ProactiveCopilotPanel({
  onSendMessage,
}: {
  onSendMessage: (message: string) => void;
}) {
  const pathname = typeof window === 'undefined' ? '/dashboard' : window.location.pathname;
  const { data } = useInboxActions(8);

  const insights = useMemo(() => {
    const actionInsights = buildActionInsights(data?.items ?? []);
    const contextual = routeInsights(pathname);
    return [...actionInsights, ...contextual].slice(0, 4);
  }, [data?.items, pathname]);

  const navigate = (href: string) => {
    window.history.pushState({}, '', href);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <section className="mx-4 mt-4 rounded-lg border bg-background/80 p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Bot className="h-4 w-4 text-primary" />
            AI 副驾
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            我先帮你把当前页面可行动的事挑出来。
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => navigate('/dashboard')}>
          行动台
        </Button>
      </div>

      <div className="space-y-2">
        {insights.map((insight) => {
          const Icon = insight.icon;
          return (
            <article
              key={insight.id}
              className="rounded-lg border bg-card p-3 transition-colors hover:bg-accent/40"
            >
              <div className="flex gap-3">
                <div
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                    insight.tone,
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold leading-5">{insight.title}</h3>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {insight.description}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => onSendMessage(insight.prompt)}
                    >
                      <Sparkles className="mr-1 h-3.5 w-3.5" />
                      让 AI 分析
                    </Button>
                    {insight.href && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => navigate(insight.href)}
                      >
                        查看
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
