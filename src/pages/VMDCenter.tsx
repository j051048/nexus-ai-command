import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Check,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  DatabaseZap,
  ListChecks,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";

import {
  GROWTH_OPERATING_MODEL_VERSION,
  GROWTH_WORKSPACE_ROUTES,
  viewFromPath,
  type GrowthWorkspaceView,
} from "@/config/growthOperatingModel";
import {
  useGrowthCommand,
  type GrowthAccount,
  type GrowthAction,
  type GrowthMetrics,
  type GrowthPriority,
  type GrowthRisk,
  type GrowthSignal,
  type GrowthTender,
} from "@/hooks/useGrowthCommand";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const PRIORITY_LABELS: Record<GrowthPriority, string> = {
  urgent: "紧急",
  high: "高优先级",
  medium: "常规",
  low: "低优先级",
};

const RISK_LABELS: Record<GrowthRisk, string> = {
  high: "高风险",
  medium: "需关注",
  low: "正常",
};

const VIEW_COPY: Record<GrowthWorkspaceView, { eyebrow: string; title: string; description: string }> = {
  today: {
    eyebrow: "AI 增长作战室",
    title: "今天最值得推进的业务",
    description: "按业务价值、时间节点与证据完整度排序，所有外部动作仍由你确认。",
  },
  radar: {
    eyebrow: "线索雷达",
    title: "值得核验的行业信号",
    description: "统一查看市场线索、客户停滞与投标节点，来源与证据保持可追溯。",
  },
  accounts: {
    eyebrow: "客户与项目",
    title: "围绕下一步推进客户",
    description: "优先显示停滞风险、预计价值和明确动作，完整档案仍在 CRM 中维护。",
  },
  tenders: {
    eyebrow: "投标作战",
    title: "在截止日前暴露关键缺口",
    description: "聚焦剩余时间、合规状态与胜率信号，高风险提交必须人工确认。",
  },
  review: {
    eyebrow: "经营复盘",
    title: "用业务结果证明 AI 价值",
    description: "区分真实业务记录与运营估算，关注行动采纳、任务完成和结果证据。",
  },
};

function money(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function PriorityBadge({ priority }: { priority: GrowthPriority }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-sm px-1.5 font-normal",
        priority === "urgent" && "border-red-200 bg-red-50 text-red-700",
        priority === "high" && "border-amber-200 bg-amber-50 text-amber-700",
      )}
    >
      {PRIORITY_LABELS[priority]}
    </Badge>
  );
}

function RiskBadge({ risk }: { risk: GrowthRisk }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs",
        risk === "high" ? "text-red-700" : risk === "medium" ? "text-amber-700" : "text-emerald-700",
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {RISK_LABELS[risk]}
    </span>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center border-t border-border/70 px-6 text-center">
      <Check className="mb-3 h-5 w-5 text-emerald-600" />
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

function MetricStrip({ metrics }: { metrics: GrowthMetrics }) {
  const items = [
    ["待核验机会", metrics.open_opportunities, Target],
    ["机会金额", money(metrics.pipeline_value), CircleDollarSign],
    ["高优信号", metrics.high_priority_signals, AlertTriangle],
    ["执行中任务", metrics.active_tasks, ListChecks],
    ["进行中投标", metrics.active_tenders, Clock3],
  ] as const;
  return (
    <div className="grid border-y border-border/80 sm:grid-cols-3 xl:grid-cols-5" data-testid="growth-metric-strip">
      {items.map(([label, value, Icon], index) => (
        <div key={label} className={cn("px-4 py-3", index > 0 && "sm:border-l sm:border-border/70")}>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icon className="h-3.5 w-3.5" />
            {label}
          </div>
          <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
        </div>
      ))}
    </div>
  );
}

function ActionRow({ action, onOpen }: { action: GrowthAction; onOpen: (url: string) => void }) {
  return (
    <article className="grid gap-3 border-b border-border/70 px-4 py-4 last:border-b-0 md:grid-cols-[auto_1fr_auto] md:items-start">
      <PriorityBadge priority={action.priority} />
      <div className="min-w-0">
        <div className="font-medium text-foreground">{action.title}</div>
        <p className="mt-1 text-sm text-foreground/80">{action.recommendation}</p>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{action.reason}</span>
          <span className="inline-flex items-center gap-1">
            <ShieldCheck className="h-3.5 w-3.5" />
            {action.confidence === "high" ? "高置信" : "中等置信"}
          </span>
          {action.execution_mode === "confirm" && <span>执行前确认</span>}
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => onOpen(action.target_url)}>
        处理
        <ChevronRight className="ml-1 h-4 w-4" />
      </Button>
    </article>
  );
}

function TodayView({ actions, onOpen }: { actions: GrowthAction[]; onOpen: (url: string) => void }) {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <section className="overflow-hidden rounded-md border border-border bg-card" aria-labelledby="today-actions-title">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 id="today-actions-title" className="font-semibold">优先行动</h2>
            <p className="text-xs text-muted-foreground">只展示当前最值得推进的 8 项</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => onOpen("/vmd/tasks?new=1")}>
            新建作战任务
          </Button>
        </div>
        {actions.length ? actions.map((action) => <ActionRow key={action.id} action={action} onOpen={onOpen} />) : (
          <EmptyState title="当前没有高优先级行动" description="可以转到线索雷达核验新信号，或创建一个明确结果的增长任务。" />
        )}
      </section>

      <aside className="space-y-5 border-l-0 xl:border-l xl:border-border/70 xl:pl-6">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium">
            <Bot className="h-4 w-4" />
            作战原则
          </div>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            <li>先核验证据，再生成内容。</li>
            <li>先推进高价值客户，再扩大触达。</li>
            <li>外发、报价与投标提交必须确认。</li>
          </ul>
        </div>
        <div className="border-t border-border/70 pt-5">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Route className="h-4 w-4" />
            完整能力
          </div>
          <div className="mt-3 space-y-2 text-sm">
            <button className="flex w-full items-center justify-between text-left text-muted-foreground hover:text-foreground" onClick={() => onOpen("/vmd/tasks")}>
              任务与交付物 <ArrowRight className="h-3.5 w-3.5" />
            </button>
            <button className="flex w-full items-center justify-between text-left text-muted-foreground hover:text-foreground" onClick={() => onOpen("/industry-knowledge")}>
              行业知识资产 <ArrowRight className="h-3.5 w-3.5" />
            </button>
            <button className="flex w-full items-center justify-between text-left text-muted-foreground hover:text-foreground" onClick={() => onOpen("/vmd/agents")}>
              Agent 与策略 <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function SignalRow({ signal, onOpen }: { signal: GrowthSignal; onOpen: (url: string) => void }) {
  return (
    <article className="grid gap-3 border-b border-border/70 px-4 py-4 last:border-b-0 md:grid-cols-[120px_1fr_140px_auto] md:items-center">
      <div><PriorityBadge priority={signal.priority} /></div>
      <div className="min-w-0">
        <div className="font-medium">{signal.title}</div>
        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{signal.summary}</p>
        <p className="mt-1 text-xs text-muted-foreground">{signal.source_label} · {signal.evidence.length} 条证据</p>
      </div>
      <div className="text-sm font-medium">{signal.estimated_value ? money(signal.estimated_value) : "金额待确认"}</div>
      <Button variant="ghost" size="icon" title="查看信号" onClick={() => onOpen(signal.target_url)}>
        <ChevronRight className="h-4 w-4" />
      </Button>
    </article>
  );
}

function RadarView({ signals, onOpen }: { signals: GrowthSignal[]; onOpen: (url: string) => void }) {
  return (
    <section className="overflow-hidden rounded-md border border-border bg-card">
      <div className="grid grid-cols-[120px_1fr_140px_40px] border-b border-border bg-muted/30 px-4 py-2 text-xs text-muted-foreground max-md:hidden">
        <span>优先级</span><span>信号与依据</span><span>潜在金额</span><span />
      </div>
      {signals.length ? signals.map((signal) => <SignalRow key={signal.id} signal={signal} onOpen={onOpen} />) : (
        <EmptyState title="暂无需要核验的信号" description="启用行业数据连接器后，新信号会与 CRM 和投标节点统一进入这里。" />
      )}
    </section>
  );
}

function AccountRow({ account, onOpen }: { account: GrowthAccount; onOpen: (url: string) => void }) {
  return (
    <tr className="border-b border-border/70 last:border-b-0">
      <td className="px-4 py-3">
        <div className="font-medium">{account.name}</div>
        <div className="text-xs text-muted-foreground">{account.industry || "行业待补充"}</div>
      </td>
      <td className="px-4 py-3 text-sm">{account.stage}</td>
      <td className="px-4 py-3 text-sm"><RiskBadge risk={account.risk} /></td>
      <td className="px-4 py-3 text-sm">{account.next_action}</td>
      <td className="px-4 py-3 text-right text-sm font-medium">{money(account.estimated_value)}</td>
      <td className="px-3 py-3 text-right">
        <Button variant="ghost" size="icon" title="打开客户" onClick={() => onOpen(account.target_url)}><ChevronRight className="h-4 w-4" /></Button>
      </td>
    </tr>
  );
}

function AccountsView({ accounts, onOpen }: { accounts: GrowthAccount[]; onOpen: (url: string) => void }) {
  if (!accounts.length) return <section className="rounded-md border border-border bg-card"><EmptyState title="还没有客户数据" description="从线索转化客户，或在 CRM 中导入现有客户后，这里会自动形成推进队列。" /></section>;
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-card">
      <table className="w-full min-w-[820px] text-left">
        <thead className="border-b border-border bg-muted/30 text-xs text-muted-foreground">
          <tr><th className="px-4 py-2 font-medium">客户</th><th className="px-4 py-2 font-medium">阶段</th><th className="px-4 py-2 font-medium">健康</th><th className="px-4 py-2 font-medium">建议下一步</th><th className="px-4 py-2 text-right font-medium">机会金额</th><th /></tr>
        </thead>
        <tbody>{accounts.map((account) => <AccountRow key={account.id} account={account} onOpen={onOpen} />)}</tbody>
      </table>
    </div>
  );
}

function TenderRow({ tender, onOpen }: { tender: GrowthTender; onOpen: (url: string) => void }) {
  return (
    <article className="grid gap-3 border-b border-border/70 px-4 py-4 last:border-b-0 lg:grid-cols-[1fr_120px_120px_110px_auto] lg:items-center">
      <div>
        <div className="font-medium">{tender.name}</div>
        <p className="mt-1 text-xs text-muted-foreground">{tender.client_name || "采购方待确认"}</p>
      </div>
      <div className="text-sm">{tender.days_left === undefined || tender.days_left === null ? "日期待确认" : `${tender.days_left} 天`}</div>
      <RiskBadge risk={tender.risk} />
      <div className="text-sm">胜率 {tender.win_probability}%</div>
      <Button variant="outline" size="sm" onClick={() => onOpen(tender.target_url)}>进入投标台</Button>
    </article>
  );
}

function TendersView({ tenders, onOpen }: { tenders: GrowthTender[]; onOpen: (url: string) => void }) {
  return (
    <section className="overflow-hidden rounded-md border border-border bg-card">
      {tenders.length ? tenders.map((tender) => <TenderRow key={tender.id} tender={tender} onOpen={onOpen} />) : (
        <EmptyState title="暂无进行中的投标项目" description="从投标分析页创建项目后，截止节点、合规状态和胜率会汇总到这里。" />
      )}
    </section>
  );
}

function ReviewView({ data }: { data: NonNullable<ReturnType<typeof useGrowthCommand>["data"]> }) {
  const reviewItems = [
    ["归因收入", money(data.review.attributed_revenue), ""],
    ["有效线索", data.review.qualified_leads, "条"],
    ["完成增长任务", data.review.completed_growth_tasks, "次"],
    ["采纳 AI 行动", data.review.accepted_actions, "次"],
    ["行动采纳率", data.review.action_adoption_rate, "%"],
    ["估算节省时间", data.review.estimated_hours_saved, "小时"],
  ] as const;
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section className="rounded-md border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="font-semibold">本期结果</h2>
          <p className="text-xs text-muted-foreground">采用、完成与业务结果分开计算</p>
        </div>
        <div className="grid sm:grid-cols-2">
          {reviewItems.map(([label, value, unit], index) => (
            <div key={label} className={cn("px-5 py-5", index % 2 === 1 && "sm:border-l sm:border-border/70", index >= 2 && "border-t border-border/70")}>
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="mt-2 text-2xl font-semibold">{value}<span className="ml-1 text-sm font-normal text-muted-foreground">{unit}</span></p>
            </div>
          ))}
        </div>
        <p className="border-t border-border/70 px-5 py-3 text-xs text-muted-foreground">{data.review.evidence_note} 当前有 {data.review.outcome_evidence_count} 条结果证据。</p>
      </section>
      <aside className="space-y-5">
        <div className="border-b border-border/70 pb-5">
          <div className="flex items-center gap-2 text-sm font-medium"><DatabaseZap className="h-4 w-4" />业务上下文图</div>
          <div className="mt-3 flex gap-6 text-sm"><span><strong>{data.context_graph.nodes}</strong> 节点</span><span><strong>{data.context_graph.links}</strong> 关系</span></div>
        </div>
        <div>
          <div className="flex items-center gap-2 text-sm font-medium"><Sparkles className="h-4 w-4" />可复制作战模板</div>
          <div className="mt-3 space-y-3">
            {data.playbooks.slice(0, 4).map((playbook) => (
              <div key={playbook.key}>
                <p className="text-sm font-medium">{playbook.name}</p>
                <p className="text-xs text-muted-foreground">{playbook.outcome}</p>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

export default function VMDCenter() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeView = viewFromPath(location.pathname);
  const copy = VIEW_COPY[activeView];
  const query = useGrowthCommand();
  const data = query.data;
  const degradedSources = data ? Object.entries(data.source_health).filter(([, status]) => status === "degraded").length : 0;

  const renderView = () => {
    if (!data) return null;
    if (activeView === "radar") return <RadarView signals={data.signals} onOpen={navigate} />;
    if (activeView === "accounts") return <AccountsView accounts={data.accounts} onOpen={navigate} />;
    if (activeView === "tenders") return <TendersView tenders={data.tenders} onOpen={navigate} />;
    if (activeView === "review") return <ReviewView data={data} />;
    return <TodayView actions={data.actions} onOpen={navigate} />;
  };

  return (
    <main className="mx-auto w-full max-w-[1380px] space-y-5 pb-20" data-testid="growth-command-center">
      <header className="flex flex-col gap-4 border-b border-border/80 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-primary"><Sparkles className="h-3.5 w-3.5" />{copy.eyebrow}</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-normal text-foreground">{copy.title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{copy.description}</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {degradedSources > 0 ? <span className="text-amber-700">{degradedSources} 个数据源降级</span> : <span className="text-emerald-700">数据源正常</span>}
          <Button variant="ghost" size="icon" title="刷新" onClick={() => query.refetch()} disabled={query.isFetching}><RefreshCw className={cn("h-4 w-4", query.isFetching && "animate-spin")} /></Button>
        </div>
      </header>

      <nav className="flex gap-1 overflow-x-auto border-b border-border/80" aria-label="增长作战视图">
        {GROWTH_WORKSPACE_ROUTES.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.key} onClick={() => navigate(item.path)} className={cn("flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm transition-colors", activeView === item.key ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
              <Icon className="h-4 w-4" />{item.label}
            </button>
          );
        })}
      </nav>

      {query.isLoading && <div className="space-y-3"><Skeleton className="h-20 w-full" /><Skeleton className="h-72 w-full" /></div>}
      {query.isError && (
        <section className="flex min-h-64 flex-col items-center justify-center rounded-md border border-border bg-card px-6 text-center">
          <AlertTriangle className="mb-3 h-5 w-5 text-amber-600" />
          <p className="font-medium">作战数据暂时不可用</p>
          <p className="mt-1 text-sm text-muted-foreground">现有 CRM、VMD 与投标功能仍可单独使用。</p>
          <Button className="mt-4" variant="outline" onClick={() => query.refetch()}>重新加载</Button>
        </section>
      )}
      {data && <MetricStrip metrics={data.metrics} />}
      {data && renderView()}

      {data && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border/70 pt-4 text-xs text-muted-foreground">
          <span>{GROWTH_OPERATING_MODEL_VERSION} · {data.capabilities.filter((item) => item.status === "ready").length} 项能力就绪</span>
          <span>演示数据隔离：{data.sandbox.production_data_mixed ? "异常" : "正常"}</span>
        </footer>
      )}
    </main>
  );
}
