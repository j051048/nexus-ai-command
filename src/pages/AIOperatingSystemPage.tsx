import { Link } from 'react-router-dom';
import {
  AGENT_TEMPLATES,
  AI_NATIVE_SCENES,
  AI_OPERATING_CAPABILITIES,
  AUTONOMOUS_ACTION_POLICIES,
  CONTEXT_GRAPH_EDGES,
  DEMO_WORKSPACE_ARTIFACTS,
  EVENT_TRIGGER_BLUEPRINTS,
  OPERATING_SYSTEM_METRICS,
  ROLE_WORKBENCH_PROFILES,
  SEVEN_DAY_SUCCESS_PATH,
  type OperatingCapability,
} from '@/config/aiOperatingSystem';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowRight, CheckCircle2, Sparkles } from 'lucide-react';

const STATUS_LABEL = {
  live: '已上线',
  ready: '可落地',
  next: '下一步',
};

const PRIORITY_TONE = {
  P0: 'border-red-500/30 bg-red-500/10 text-red-600',
  P1: 'border-orange-500/30 bg-orange-500/10 text-orange-600',
  P2: 'border-blue-500/30 bg-blue-500/10 text-blue-600',
  P3: 'border-violet-500/30 bg-violet-500/10 text-violet-600',
  P4: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600',
  P5: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-600',
  P6: 'border-slate-500/30 bg-slate-500/10 text-slate-600',
};

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function CapabilityCard({ item }: { item: OperatingCapability }) {
  const Icon = item.icon;
  return (
    <article className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg', PRIORITY_TONE[item.priority])}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={PRIORITY_TONE[item.priority]}>
                {item.priority}
              </Badge>
              <Badge variant={item.status === 'live' ? 'default' : 'secondary'}>
                {STATUS_LABEL[item.status]}
              </Badge>
            </div>
            <h3 className="mt-2 text-base font-semibold">{item.title}</h3>
          </div>
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.description}</p>
      <div className="mt-3 rounded-md bg-muted/50 p-3 text-xs leading-5 text-muted-foreground">
        <span className="font-medium text-foreground">落地证据：</span>
        {item.proof}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild size="sm" variant="outline">
          <Link to={item.href}>
            打开入口
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
        <Button size="sm" variant="ghost" onClick={() => triggerAI(item.aiPrompt)}>
          <Sparkles className="mr-2 h-4 w-4" />
          让 AI 生成方案
        </Button>
      </div>
    </article>
  );
}

export default function AIOperatingSystemPage() {
  const p0p3 = AI_OPERATING_CAPABILITIES.filter((item) => ['P0', 'P1', 'P2', 'P3'].includes(item.priority));
  const p4p6 = AI_OPERATING_CAPABILITIES.filter((item) => ['P4', 'P5', 'P6'].includes(item.priority));

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      <section className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <Sparkles className="h-4 w-4" />
              Nexus AI Operating System
            </div>
            <h1 className="text-2xl font-bold tracking-tight">
              科学仪器销售团队的 AI 作战室
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              这不是继续增加模块，而是把 P0-P6 收敛为一套产品形态：VMD 超级场景、Agent 生命周期、业务知识图谱、价值证明、首周成功路径、Demo 空间和角色化工作台。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link to="/vmd">进入 VMD 超级场景</Link>
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                triggerAI('请基于 Nexus 当前 P0-P6 产品形态，生成一个面向科学仪器销售团队的上线实施路线图。')
              }
            >
              <Sparkles className="mr-2 h-4 w-4" />
              生成实施路线图
            </Button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          {OPERATING_SYSTEM_METRICS.map((metric) => {
            const Icon = metric.icon;
            return (
              <div key={metric.label} className="rounded-lg border bg-background/60 p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Icon className="h-4 w-4 text-primary" />
                  {metric.label}
                </div>
                <div className="mt-2 text-lg font-semibold">{metric.value}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">P0-P3：AI 原生能力底座</h2>
            <p className="text-sm text-muted-foreground">
              先做深超级场景，再补 Agent 可测试、可定义、可观测、可自动执行。
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {p0p3.map((item) => (
              <CapabilityCard key={item.title} item={item} />
            ))}
          </div>
        </div>

        <aside className="space-y-4">
          <section className="rounded-lg border bg-card p-4 shadow-sm">
            <h2 className="font-semibold">Context Graph 最小闭环</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              学 Glean 的关键不是连接器数量，而是先把已有业务实体连成可注入 Agent 的上下文图谱。
            </p>
            <div className="mt-3 space-y-2">
              {CONTEXT_GRAPH_EDGES.map((edge) => (
                <div key={edge} className="rounded-md border bg-background/60 px-3 py-2 text-sm">
                  {edge}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border bg-card p-4 shadow-sm">
            <h2 className="font-semibold">自主行动策略</h2>
            <div className="mt-3 space-y-3">
              {AUTONOMOUS_ACTION_POLICIES.map((policy) => (
                <div key={policy.level} className="rounded-md border bg-background/60 p-3">
                  <div className="font-medium">{policy.level}</div>
                  <p className="mt-1 text-sm leading-5 text-muted-foreground">{policy.scope}</p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{policy.guardrail}</p>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">P4-P6：产品形态与增长闭环</h2>
          <p className="text-sm text-muted-foreground">
            让用户第一眼知道该做什么，让售前能演示，让团队按角色长期留下来。
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {p4p6.map((item) => (
            <CapabilityCard key={item.title} item={item} />
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-semibold">AI-Native 场景</h2>
          <div className="mt-3 space-y-3">
            {AI_NATIVE_SCENES.map((scene) => {
              const Icon = scene.icon;
              return (
                <div key={scene.title} className="rounded-md border bg-background/60 p-3">
                  <div className="flex items-center gap-2 font-medium">
                    <Icon className="h-4 w-4 text-primary" />
                    {scene.title}
                  </div>
                  <p className="mt-1 text-sm leading-5 text-muted-foreground">{scene.flow}</p>
                  <Badge className="mt-2" variant="outline">{scene.metric}</Badge>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-semibold">7 天成功路径</h2>
          <div className="mt-3 space-y-2">
            {SEVEN_DAY_SUCCESS_PATH.map((step) => (
              <div key={step} className="flex gap-2 rounded-md border bg-background/60 p-3 text-sm leading-5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>

        <div id="demo-space" className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-semibold">科学仪器 Demo 空间</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            售前演示不从空库开始，而是从一套可讲完整闭环的行业样板间开始。
          </p>
          <div className="mt-3 space-y-3">
            {DEMO_WORKSPACE_ARTIFACTS.map((artifact) => (
              <div key={artifact.title} className="rounded-md border bg-background/60 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{artifact.title}</span>
                  <Badge variant="secondary">{artifact.count}</Badge>
                </div>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{artifact.example}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold">行业 Agent 模板库</h2>
            <Button asChild size="sm" variant="outline">
              <Link to="/industry-knowledge">打开行业资产</Link>
            </Button>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {AGENT_TEMPLATES.map((template) => (
              <div key={template.id} className="rounded-md border bg-background/60 p-3">
                <div className="font-medium">{template.title}</div>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{template.scenario}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {template.installs.map((item) => (
                    <span key={item} className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                      {item}
                    </span>
                  ))}
                </div>
                <Button
                  className="mt-3"
                  size="sm"
                  variant="ghost"
                  onClick={() => triggerAI(template.aiPrompt)}
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  生成安装方案
                </Button>
              </div>
            ))}
          </div>
        </div>

        <div id="role-workbench" className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="font-semibold">角色化作战台</h2>
          <div className="mt-3 space-y-3">
            {ROLE_WORKBENCH_PROFILES.map((profile) => (
              <div key={profile.role} className="rounded-md border bg-background/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{profile.role}</span>
                  <span className="text-xs text-muted-foreground">{profile.focus}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {profile.firstScreen.map((item) => (
                    <span key={item} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                      {item}
                    </span>
                  ))}
                </div>
                <Button
                  className="mt-3"
                  size="sm"
                  variant="ghost"
                  onClick={() => triggerAI(profile.aiDefault)}
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  使用默认 AI
                </Button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <h2 className="font-semibold">事件驱动 Agent 触发蓝图</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {EVENT_TRIGGER_BLUEPRINTS.map((trigger) => (
            <div key={trigger} className="rounded-md border bg-background/60 p-3 text-sm leading-6">
              {trigger}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
