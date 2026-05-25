import { useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Inbox,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useInboxAnalytics, type ActionSource } from '@/hooks/useInboxActions';
import { cn } from '@/lib/utils';

const SOURCE_LABELS: Record<ActionSource, string> = {
  approval: '审批',
  notification: '通知',
  crm: '客户风险',
  system: '系统',
};

function percent(value: number) {
  return `${Math.round((Number.isFinite(value) ? value : 0) * 100)}%`;
}

function formatTime(value?: string | null) {
  if (!value) return '未知时间';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未知时间';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

export default function ActionAnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError, refetch } = useInboxAnalytics(days);
  const summary = data?.summary;

  const sourceRows = useMemo(
    () =>
      Object.entries(data?.by_source ?? {}).map(([source, stats]) => ({
        source: source as ActionSource,
        ...stats,
      })),
    [data?.by_source],
  );
  const trendRows = data?.daily_trend ?? [];
  const maxTrendTotal = Math.max(1, ...trendRows.map((row) => row.total));

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
            <Activity className="h-4 w-4" />
            行动台运营分析
          </div>
          <h1 className="text-2xl font-bold tracking-tight">AI 建议是否真的推动了业务动作</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            跟踪行动项被采纳、完成、稍后和忽略的情况，发现高风险未闭环事项，并持续校准 AI 建议质量。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {[7, 30, 90].map((value) => (
            <Button
              key={value}
              size="sm"
              variant={days === value ? 'default' : 'outline'}
              onClick={() => setDays(value)}
            >
              {value} 天
            </Button>
          ))}
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              triggerAI(`请分析最近 ${days} 天行动台数据，指出团队执行力风险和 AI 建议需要优化的地方。`)
            }
          >
            <Sparkles className="mr-2 h-4 w-4" />
            AI 复盘
          </Button>
        </div>
      </header>

      {isLoading && <div className="h-56 animate-pulse rounded-lg bg-muted" />}

      {isError && (
        <section className="rounded-lg border border-destructive/30 bg-destructive/10 p-5">
          <div className="font-medium text-destructive">行动分析加载失败</div>
          <p className="mt-1 text-sm text-muted-foreground">
            请确认 action_events migration 已执行，且 `/api/inbox/analytics` 可访问。
          </p>
          <Button className="mt-4" variant="outline" onClick={() => refetch()}>
            重新加载
          </Button>
        </section>
      )}

      {!isLoading && !isError && summary && (
        <>
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {[
              {
                label: '行动事件',
                value: summary.total_events,
                icon: Inbox,
                tone: 'bg-blue-500/10 text-blue-600',
              },
              {
                label: '采纳率',
                value: percent(summary.acceptance_rate),
                icon: TrendingUp,
                tone: 'bg-emerald-500/10 text-emerald-600',
              },
              {
                label: '完成率',
                value: percent(summary.completion_rate),
                icon: CheckCircle2,
                tone: 'bg-cyan-500/10 text-cyan-600',
              },
              {
                label: '忽略率',
                value: percent(summary.ignored_rate),
                icon: Clock,
                tone: 'bg-amber-500/10 text-amber-600',
              },
              {
                label: '高风险未闭环',
                value: summary.open_high_risk,
                icon: AlertTriangle,
                tone: 'bg-red-500/10 text-red-600',
              },
            ].map((card) => {
              const Icon = card.icon;
              return (
                <div key={card.label} className="rounded-lg border bg-card p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-xs text-muted-foreground">{card.label}</div>
                      <div className="mt-2 text-2xl font-bold">{card.value}</div>
                    </div>
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', card.tone)}>
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                </div>
              );
            })}
          </section>

          <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold">来源转化表现</h2>
                <Badge variant="outline">{data?.window_days} 天窗口</Badge>
              </div>
              <div className="space-y-3">
                {sourceRows.length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无行动事件，开始处理行动项后这里会出现趋势。</p>
                ) : (
                  sourceRows.map((row) => {
                    const handled = row.accepted + row.completed + row.command_executed;
                    const width = row.total > 0 ? Math.min(100, Math.round((handled / row.total) * 100)) : 0;
                    return (
                      <div key={row.source} className="rounded-lg border bg-background/60 p-3">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">{SOURCE_LABELS[row.source]}</span>
                          <span className="text-muted-foreground">{handled}/{row.total} 已推动</span>
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span>采纳 {row.accepted}</span>
                          <span>完成 {row.completed + row.command_executed}</span>
                          <span>稍后 {row.snoozed}</span>
                          <span>忽略 {row.ignored}</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold">高风险未闭环</h2>
                <Button size="sm" variant="ghost" onClick={() => triggerAI('请把高风险未闭环行动整理成今天的处理清单。')}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  生成清单
                </Button>
              </div>
              <div className="space-y-3">
                {(data?.stale_open_actions ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无高风险未闭环行动。</p>
                ) : (
                  data!.stale_open_actions.slice(0, 8).map((item) => (
                    <div key={item.id} className="rounded-lg border bg-background/60 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{SOURCE_LABELS[item.source]}</Badge>
                        <Badge variant={item.priority === 'urgent' ? 'destructive' : 'secondary'}>
                          {item.priority}
                        </Badge>
                      </div>
                      <div className="mt-2 text-sm font-medium">{item.title}</div>
                      {item.reason && <div className="mt-1 text-xs text-muted-foreground">{item.reason}</div>}
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold">行动趋势</h2>
                <Badge variant="outline">按天聚合</Badge>
              </div>
              {trendRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无趋势数据。</p>
              ) : (
                <div className="space-y-2">
                  {trendRows.slice(-14).map((row) => {
                    const width = Math.max(4, Math.round((row.total / maxTrendTotal) * 100));
                    return (
                      <div key={row.date} className="grid grid-cols-[84px_1fr_52px] items-center gap-3 text-sm">
                        <span className="text-xs text-muted-foreground">{row.date.slice(5)}</span>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
                        </div>
                        <span className="text-right text-xs text-muted-foreground">{row.total} 次</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="rounded-lg border bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold">团队动作榜</h2>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => triggerAI('请根据团队动作榜识别执行力断点，并给出下周管理动作。')}
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  管理建议
                </Button>
              </div>
              {(data?.by_actor ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无团队动作数据。</p>
              ) : (
                <div className="space-y-2">
                  {data!.by_actor.slice(0, 6).map((actor) => (
                    <div key={actor.user_id} className="rounded-lg border bg-background/60 p-3">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="truncate font-medium">{actor.user_id}</span>
                        <Badge variant="outline">{actor.total} 次</Badge>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>采纳 {actor.accepted}</span>
                        <span>完成 {actor.completed}</span>
                        <span>忽略 {actor.ignored}</span>
                        <span>稍后 {actor.snoozed}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border bg-card p-4 shadow-sm">
            <h2 className="font-semibold">最近行动事件</h2>
            <div className="mt-3 divide-y">
              {(data?.recent_events ?? []).length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">暂无最近事件。</p>
              ) : (
                data!.recent_events.map((event) => (
                  <div key={event.id || `${event.action_id}-${event.created_at}`} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                    <div className="min-w-0">
                      <div className="font-medium">{event.action_id}</div>
                      <div className="text-xs text-muted-foreground">
                        {SOURCE_LABELS[event.source]} · {event.event_type}
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground">{formatTime(event.created_at)}</div>
                  </div>
                ))
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
