import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AGENT_TEMPLATES,
  AI_NATIVE_SCENES,
  AI_OPERATING_CAPABILITIES,
  AUTONOMOUS_ACTION_POLICIES,
  DEMO_WORKSPACE_ARTIFACTS,
  EVENT_TRIGGER_BLUEPRINTS,
  ROLE_WORKBENCH_PROFILES,
  SEVEN_DAY_SUCCESS_PATH,
  type OperatingCapability,
} from '@/config/aiOperatingSystem';
import { useAIOperatingOverview, useRunAgentSimulation } from '@/hooks/useAIOperatingSystem';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  ArrowRight,
  CheckCircle2,
  GitBranch,
  Loader2,
  Network,
  PlayCircle,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

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

const DEFAULT_SIMULATION_MESSAGES = [
  '30天未跟进客户自动生成拜访提醒和邮件草稿',
  '审批一笔12000元差旅报销并检查风险',
  '根据招标文件生成评分矩阵和技术响应草稿',
].join('\n');

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function formatPercent(value?: number) {
  if (typeof value !== 'number') return '0%';
  return `${Math.round(value * 100)}%`;
}

function CapabilityCard({ item }: { item: OperatingCapability }) {
  const Icon = item.icon;
  return (
    <article className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg', PRIORITY_TONE[item.priority])}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
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
  const [simulationInput, setSimulationInput] = useState(DEFAULT_SIMULATION_MESSAGES);
  const overview = useAIOperatingOverview(30);
  const simulation = useRunAgentSimulation();

  const p0p3 = AI_OPERATING_CAPABILITIES.filter((item) => ['P0', 'P1', 'P2', 'P3'].includes(item.priority));
  const p4p6 = AI_OPERATING_CAPABILITIES.filter((item) => ['P4', 'P5', 'P6'].includes(item.priority));

  const liveMetrics = useMemo(() => {
    const data = overview.data;
    return [
      { label: 'Agent 成功率', value: formatPercent(data?.agent.success_rate), hint: `${data?.agent.total_runs ?? 0} 次运行` },
      { label: '行动完成率', value: formatPercent(data?.actions.completion_rate), hint: `${data?.actions.total_events ?? 0} 条事件` },
      { label: '图谱节点', value: String(data?.graph.summary.node_count ?? 0), hint: `${data?.graph.summary.edge_count ?? 0} 条关系` },
      { label: 'Token 消耗', value: String(data?.agent.total_tokens ?? 0), hint: `$${data?.agent.total_cost_usd ?? 0}` },
    ];
  }, [overview.data]);

  const runSimulation = () => {
    simulation.mutate({
      messages: simulationInput
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
      candidate_policy: '低风险动作自动执行；审批、合同、外发、付款、删除和批量动作进入人工确认。',
    });
  };

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      <section className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <Sparkles className="h-4 w-4" />
              Nexus AI Operating System
            </div>
            <h1 className="text-2xl font-bold tracking-tight">科学仪器销售团队的 AI 作战室</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              这里把 P0-P6 从产品蓝图升级为运营控制台：实时读取 Agent 运行、行动事件和业务知识图谱，并提供可灰度的 Agent 仿真沙盒。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link to="/vmd">进入 VMD 超级场景</Link>
            </Button>
            <Button
              variant="outline"
              onClick={() => triggerAI('基于当前 Agent 运行、行动事件和业务知识图谱，生成今天的科学仪器销售作战建议。')}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              生成今日作战建议
            </Button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {liveMetrics.map((metric) => (
            <div key={metric.label} className="rounded-lg border bg-background/60 p-3">
              <div className="text-xs text-muted-foreground">{metric.label}</div>
              <div className="mt-2 text-xl font-semibold">{metric.value}</div>
              <div className="mt-1 text-xs text-muted-foreground">{metric.hint}</div>
            </div>
          ))}
        </div>
        {overview.isError && (
          <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700">
            真实运营数据暂时不可用，页面已保留产品蓝图。请确认 `/api/ai-operating-system/overview` 可访问。
          </div>
        )}
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-primary" />
            <h2 className="font-semibold">真实运营数据</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            这块数据来自 `agent_runs`、`action_events` 和业务实体表，用来证明 AI 作战系统不是静态蓝图。
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border bg-background/60 p-3">
              <div className="text-sm font-medium">Agent 生命周期</div>
              <div className="mt-2 text-xs leading-5 text-muted-foreground">
                完成 {overview.data?.agent.completed ?? 0} 次，失败 {overview.data?.agent.failed ?? 0} 次，失败率 {formatPercent(overview.data?.agent.failure_rate)}。
              </div>
            </div>
            <div className="rounded-md border bg-background/60 p-3">
              <div className="text-sm font-medium">行动闭环</div>
              <div className="mt-2 text-xs leading-5 text-muted-foreground">
                采纳 {overview.data?.actions.accepted ?? 0} 次，完成 {overview.data?.actions.completed ?? 0} 次，忽略 {overview.data?.actions.ignored ?? 0} 次。
              </div>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {(overview.data?.recent_runs ?? []).slice(0, 4).map((run) => (
              <div key={run.id || run.run_id} className="rounded-md border bg-background/60 px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{run.input_summary || run.run_id || '未命名运行'}</span>
                  <Badge variant="outline">{run.status || 'unknown'}</Badge>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <PlayCircle className="h-4 w-4 text-primary" />
            <h2 className="font-semibold">Agent 仿真沙盒</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            输入历史用户消息或灰度样例，对比“只推荐”和“低风险自动执行”的行为差异，先仿真再上线。
          </p>
          <Textarea
            className="mt-3 min-h-28"
            value={simulationInput}
            onChange={(event) => setSimulationInput(event.target.value)}
          />
          <Button className="mt-3" onClick={runSimulation} disabled={simulation.isPending}>
            {simulation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            运行仿真
          </Button>
          {simulation.data && (
            <div className="mt-4 space-y-3">
              <div className="grid gap-2 md:grid-cols-4">
                <Badge variant="secondary">样例 {simulation.data.summary.case_count}</Badge>
                <Badge variant="secondary">自动化 {formatPercent(simulation.data.summary.automation_rate)}</Badge>
                <Badge variant="secondary">人工确认 {formatPercent(simulation.data.summary.hitl_rate)}</Badge>
                <Badge variant="outline">{simulation.data.summary.recommendation}</Badge>
              </div>
              {simulation.data.cases.slice(0, 3).map((item) => (
                <div key={item.id} className="rounded-md border bg-background/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium">{item.detected_intent}</span>
                    <Badge variant={item.candidate.mode === 'auto' ? 'default' : 'secondary'}>
                      {item.candidate.mode === 'auto' ? '自动执行' : '人工确认'}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm leading-5 text-muted-foreground">{item.message}</p>
                  <div className="mt-2 text-xs text-muted-foreground">
                    工具链：{item.suggested_tools.join(' → ')}；风险分 {item.risk_score}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
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
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-primary" />
              <h2 className="font-semibold">Context Graph 最小闭环</h2>
            </div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              当前图谱会注入 Agent Context：客户、线索、项目、合同、审批、文档和行动事件会被串成关系，而不是只做文档检索。
            </p>
            <div className="mt-3 grid gap-2">
              {(overview.data?.graph.nodes ?? []).slice(0, 6).map((node) => (
                <div key={node.id} className="rounded-md border bg-background/60 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span>{node.label}</span>
                    <Badge variant="outline">{node.type}</Badge>
                  </div>
                </div>
              ))}
              {!overview.data?.graph.nodes?.length && (
                <div className="rounded-md border bg-background/60 px-3 py-2 text-sm text-muted-foreground">
                  暂无真实图谱节点，导入客户、项目、合同或行动事件后会自动出现。
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border bg-card p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="font-semibold">自主行动策略</h2>
            </div>
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
            售前演示不从空库开始，而是从一套能讲完整闭环的行业样板间开始。
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
                <Button className="mt-3" size="sm" variant="ghost" onClick={() => triggerAI(template.aiPrompt)}>
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
                <Button className="mt-3" size="sm" variant="ghost" onClick={() => triggerAI(profile.aiDefault)}>
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
