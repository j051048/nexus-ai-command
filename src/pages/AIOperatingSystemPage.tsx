import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AGENT_TEMPLATES,
  AI_OPERATING_CAPABILITIES,
  AUTONOMOUS_ACTION_POLICIES,
  DEMO_WORKSPACE_ARTIFACTS,
  EVENT_TRIGGER_BLUEPRINTS,
} from '@/config/aiOperatingSystem';
import {
  type AgentDefinitionResult,
  useAIOperatingOverview,
  useDefineAgentFromSop,
  useRunAgentSimulation,
} from '@/hooks/useAIOperatingSystem';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  Activity,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileCheck2,
  GitBranch,
  Library,
  Loader2,
  Network,
  PlayCircle,
  Radar,
  ShieldCheck,
  Zap,
} from 'lucide-react';

const DEFAULT_SIMULATION_MESSAGES = [
  '30天未跟进客户自动生成拜访提醒和邮件草稿',
  '审批一笔12000元差旅报销并检查风险',
  '根据招标文件生成评分矩阵和技术响应草稿',
].join('\n');

const DEFAULT_SOP_TEXT = [
  '当科学仪器客户 30 天没有跟进记录时，查询客户阶段、最近拜访、项目预算和历史沟通。',
  '客户处于报价或招投标阶段时，生成邮件草稿和下一步任务，但不直接外发。',
  '涉及合同、审批、付款、删除或批量外发时，必须进入人工确认。',
  '每次建议必须引用客户、项目、合同、文档或行动事件作为证据。',
].join('\n');

const RELEASE_STEPS = [
  { label: '定义 SOP', icon: FileCheck2 },
  { label: '仿真验证', icon: PlayCircle },
  { label: '人工审阅', icon: ShieldCheck },
  { label: '灰度上线', icon: Zap },
];

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function formatPercent(value?: number) {
  if (typeof value !== 'number') return '0%';
  return `${Math.round(value * 100)}%`;
}

function statusTone(status?: string) {
  if (status === 'completed' || status === 'success') return 'text-emerald-600 bg-emerald-500/10';
  if (status === 'failed' || status === 'error') return 'text-red-600 bg-red-500/10';
  return 'text-amber-700 bg-amber-500/10';
}

function buildLocalAgentDefinition(sopText: string): AgentDefinitionResult {
  const firstLine = sopText.split('\n').map((item) => item.trim()).find(Boolean) ?? '客户跟进 SOP';
  return {
    scenario: '科学仪器客户跟进 Agent',
    autonomy_level: 'guarded_auto',
    intent_rules: [
      {
        name: 'scientific-instrument-followup',
        trigger: firstLine,
        tools: ['search_customers', 'draft_followup', 'create_task'],
        autonomy: 'guarded_auto',
      },
    ],
    operating_procedure: [
      {
        step: 1,
        name: '读取业务上下文',
        instruction: '查询客户、项目、合同、文档与行动事件，形成证据链。',
        expected_evidence: '客户/项目/合同/文档/行动事件',
      },
      {
        step: 2,
        name: '生成低风险草稿',
        instruction: '只生成跟进邮件、拜访提醒和下一步任务，不直接外发。',
        expected_evidence: '用户确认或行动事件记录',
      },
    ],
    tools: ['search_customers', 'draft_followup', 'create_task'],
    guardrails: ['合同、付款、审批、删除、批量外发必须人工确认。'],
    test_cases: ['输入：30 天未跟进客户。期望：输出证据链、邮件草稿和待确认任务。'],
    confidence: 0.68,
    next_steps: ['放入 Agent 仿真沙盒跑历史消息回放。'],
    definition_markdown: '# 科学仪器客户跟进 Agent Operating Procedure',
  };
}

export default function AIOperatingSystemPage() {
  const [activeTab, setActiveTab] = useState('command');
  const [simulationInput, setSimulationInput] = useState(DEFAULT_SIMULATION_MESSAGES);
  const [sopInput, setSopInput] = useState(DEFAULT_SOP_TEXT);
  const [draftDefinition, setDraftDefinition] = useState<AgentDefinitionResult | null>(null);
  const overview = useAIOperatingOverview(30);
  const simulation = useRunAgentSimulation();
  const agentDefinition = useDefineAgentFromSop();
  const displayedAgentDefinition = agentDefinition.data ?? draftDefinition;

  const metrics = useMemo(() => {
    const data = overview.data;
    return [
      {
        label: 'Agent 成功率',
        value: formatPercent(data?.agent.success_rate),
        meta: `${data?.agent.total_runs ?? 0} 次运行`,
        icon: Activity,
      },
      {
        label: '行动完成率',
        value: formatPercent(data?.actions.completion_rate),
        meta: `${data?.actions.completed ?? 0}/${data?.actions.total_events ?? 0} 已闭环`,
        icon: CheckCircle2,
      },
      {
        label: '信任评分',
        value: String(data?.trust.confidence_score ?? 0),
        meta: data?.trust.confidence_level ?? '待评估',
        icon: ShieldCheck,
      },
      {
        label: '本月价值',
        value: `¥${data?.value.estimated_value_cny ?? 0}`,
        meta: `节省 ${data?.value.saved_hours ?? 0} 小时`,
        icon: Radar,
      },
    ];
  }, [overview.data]);

  const actionQueue = useMemo(() => {
    const data = overview.data;
    return [
      {
        priority: '高',
        title: data?.agent.failed ? `${data.agent.failed} 次 Agent 运行需要复盘` : '验证首个 Agent 发布流程',
        detail: data?.agent.failed ? '检查失败工具、上下文与回退路径' : '先完成 SOP 定义和仿真验证',
        action: '进入仿真',
        tab: 'release',
      },
      {
        priority: '中',
        title: data?.actions.total_events ? `${data.actions.total_events - data.actions.completed} 个行动尚未闭环` : '配置第一条自动行动策略',
        detail: '低风险自动执行，高风险保留人工确认',
        action: '查看策略',
        tab: 'operations',
      },
      {
        priority: '中',
        title: data?.graph.summary.node_count ? `业务图谱已有 ${data.graph.summary.node_count} 个节点` : '补齐客户与项目上下文',
        detail: '让 Agent 的建议具备实体关系和证据来源',
        action: '查看图谱',
        tab: 'operations',
      },
    ];
  }, [overview.data]);

  const runSimulation = () => {
    simulation.mutate({
      messages: simulationInput.split('\n').map((item) => item.trim()).filter(Boolean),
      candidate_policy: '低风险动作自动执行；审批、合同、外发、付款、删除和批量动作进入人工确认。',
    });
  };

  const defineAgent = () => {
    setDraftDefinition(buildLocalAgentDefinition(sopInput));
    agentDefinition.mutate({
      scenario: '科学仪器客户跟进 Agent',
      autonomy_level: 'guarded_auto',
      sop_text: sopInput,
    });
  };

  return (
    <main className="min-h-full">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-xl font-semibold">AI 运营工作台</h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />系统运行中
              </span>
              <span>30 天运营窗口</span>
              <span>{overview.data?.agent.total_runs ?? 0} 次 Agent 运行</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => triggerAI('基于当前运营数据，生成今天最值得推进的三个科学仪器销售动作。')}>
              <Activity className="mr-2 h-4 w-4" />今日建议
            </Button>
            <Button asChild variant="secondary">
              <Link to="/agent-improvement-center">进化中心</Link>
            </Button>
            <Button asChild>
              <Link to="/vmd">进入 VMD<ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
          </div>
        </header>

        <section className="grid border-b py-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="核心指标">
          {metrics.map((metric, index) => {
            const Icon = metric.icon;
            return (
              <div key={metric.label} className={cn('flex items-center gap-3 py-3 sm:px-4 lg:py-1', index > 0 && 'lg:border-l')}>
                <div className="flex h-8 w-8 items-center justify-center rounded-md border border-border/80 bg-muted/40 text-primary shrink-0 shadow-sm">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-medium text-muted-foreground">{metric.label}</div>
                  <div className="mt-0.5 flex items-baseline gap-2">
                    <span className="font-mono text-xl font-semibold tabular-nums">{metric.value}</span>
                    <span className="truncate text-xs text-muted-foreground">{metric.meta}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </section>

        {overview.isError && (
          <div className="mt-4 flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-800">
            <CircleAlert className="h-4 w-4" />运营数据暂不可用，操作工作流仍可使用。
          </div>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-5">
          <TabsList className="grid h-10 w-full grid-cols-4 md:w-auto md:min-w-[520px]">
            <TabsTrigger value="command">工作台总览</TabsTrigger>
            <TabsTrigger value="release">Agent 发布</TabsTrigger>
            <TabsTrigger value="operations">运行监控</TabsTrigger>
            <TabsTrigger value="library">能力库</TabsTrigger>
          </TabsList>

          <TabsContent value="command" className="mt-4 space-y-4">
            <section className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
              <div className="rounded-lg border bg-background">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <div>
                    <h2 className="font-semibold">今日重点队列</h2>
                    <p className="mt-0.5 text-xs text-muted-foreground">按风险与业务影响排序</p>
                  </div>
                  <Badge variant="secondary">{actionQueue.length} 项</Badge>
                </div>
                <div className="divide-y">
                  {actionQueue.map((item, index) => (
                    <button
                      key={item.title}
                      type="button"
                      className="grid w-full grid-cols-[28px_1fr_auto] items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
                      onClick={() => setActiveTab(item.tab)}
                    >
                      <span className={cn('flex h-7 w-7 items-center justify-center rounded-md text-xs font-semibold', index === 0 ? 'bg-red-500/10 text-red-600' : 'bg-amber-500/10 text-amber-700')}>
                        {index + 1}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{item.title}</span>
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.detail}</span>
                      </span>
                      <span className="hidden items-center gap-1 text-xs font-medium text-primary sm:flex">
                        {item.action}<ChevronRight className="h-4 w-4" />
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border bg-background p-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold">AI 价值与信任仪表盘</h2>
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                </div>
                <div className="mt-5 space-y-5">
                  <div>
                    <div className="flex items-center justify-between text-sm">
                      <span>运行可信度</span>
                      <span className="font-semibold">{overview.data?.trust.confidence_score ?? 0}/100</span>
                    </div>
                    <Progress value={overview.data?.trust.confidence_score ?? 0} className="mt-2 h-2" />
                  </div>
                  <div className="grid grid-cols-3 gap-3 border-y py-4 text-center">
                    <div><div className="text-lg font-semibold">{overview.data?.value.automated_followups ?? 0}</div><div className="text-xs text-muted-foreground">自动跟进</div></div>
                    <div><div className="text-lg font-semibold">{overview.data?.value.risk_reviews ?? 0}</div><div className="text-xs text-muted-foreground">风险复核</div></div>
                    <div><div className="text-lg font-semibold">{formatPercent(overview.data?.trust.human_review_rate)}</div><div className="text-xs text-muted-foreground">人工复核</div></div>
                  </div>
                  <div className="flex items-start gap-2 text-sm text-muted-foreground">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{overview.data?.trust.audit_summary ?? '等待更多真实运行数据形成审计结论。'}</span>
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-lg border bg-background">
              <div className="flex flex-col gap-3 border-b px-4 py-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="font-semibold">Agent 发布路径</h2>
                  <p className="mt-0.5 text-xs text-muted-foreground">每次变更都经过定义、验证、审阅和灰度</p>
                </div>
                <Button size="sm" onClick={() => setActiveTab('release')}>
                  开始发布<ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
              <div className="grid gap-px bg-border md:grid-cols-4">
                {RELEASE_STEPS.map((step, index) => {
                  const Icon = step.icon;
                  return (
                    <div key={step.label} className="flex items-center gap-3 bg-background px-4 py-4">
                      <div className={cn('flex h-8 w-8 items-center justify-center rounded-md', index === 0 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div><div className="text-xs text-muted-foreground">步骤 {index + 1}</div><div className="text-sm font-medium">{step.label}</div></div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section id="demo-space" className="rounded-lg border bg-background">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div>
                  <h2 className="font-semibold">科学仪器 Demo 空间</h2>
                  <p className="mt-0.5 text-xs text-muted-foreground">用于售前演示与新团队练习</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => triggerAI('启动科学仪器销售 Demo：从客户线索开始，依次展示竞品战卡、投标分析和跟进闭环。')}>
                  启动演示<PlayCircle className="ml-2 h-4 w-4" />
                </Button>
              </div>
              <div className="grid divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
                {DEMO_WORKSPACE_ARTIFACTS.map((artifact) => (
                  <div key={artifact.title} className="px-4 py-3">
                    <div className="text-xl font-semibold">{artifact.count}</div>
                    <div className="text-sm font-medium">{artifact.title}</div>
                  </div>
                ))}
              </div>
            </section>
          </TabsContent>

          <TabsContent value="release" className="mt-4">
            <section className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-lg border bg-background">
                <div className="border-b px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs font-semibold text-primary-foreground">1</span>
                    <h2 className="font-semibold">SOP → AOP 自然语言定义器</h2>
                  </div>
                  <p className="mt-1 pl-8 text-xs text-muted-foreground">粘贴业务规则，生成触发器、工具链和安全边界</p>
                </div>
                <div className="p-4">
                  <Textarea className="min-h-40 resize-y text-sm leading-6" value={sopInput} onChange={(event) => setSopInput(event.target.value)} aria-label="Agent SOP" />
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <span className="text-xs text-muted-foreground">模式：受控自动化</span>
                    <Button onClick={defineAgent} disabled={agentDefinition.isPending}>
                      {agentDefinition.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                      生成 Agent 定义
                    </Button>
                  </div>
                  {displayedAgentDefinition && (
                    <div className="mt-4 border-t pt-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge>{displayedAgentDefinition.scenario}</Badge>
                        <Badge variant="outline">置信度 {formatPercent(displayedAgentDefinition.confidence)}</Badge>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div><div className="text-xs text-muted-foreground">触发规则</div><div className="mt-1 text-lg font-semibold">{displayedAgentDefinition.intent_rules.length}</div></div>
                        <div><div className="text-xs text-muted-foreground">工具</div><div className="mt-1 text-lg font-semibold">{displayedAgentDefinition.tools.length}</div></div>
                        <div><div className="text-xs text-muted-foreground">测试用例</div><div className="mt-1 text-lg font-semibold">{displayedAgentDefinition.test_cases.length}</div></div>
                      </div>
                      <div className="mt-4">
                        <div className="text-sm font-medium">触发规则</div>
                        <div className="mt-2 divide-y rounded-md border" data-testid="agent-definition-trigger-rules">
                          {displayedAgentDefinition.intent_rules.slice(0, 3).map((rule) => (
                            <div key={rule.name} className="flex items-start gap-2 px-3 py-2 text-sm">
                              <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /><span>{rule.trigger}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border bg-background">
                <div className="border-b px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md bg-muted text-xs font-semibold">2</span>
                    <h2 className="font-semibold">Agent 仿真沙盒</h2>
                  </div>
                  <p className="mt-1 pl-8 text-xs text-muted-foreground">用历史消息验证自动化边界与风险</p>
                </div>
                <div className="p-4">
                  <Textarea className="min-h-40 resize-y text-sm leading-6" value={simulationInput} onChange={(event) => setSimulationInput(event.target.value)} aria-label="仿真消息" />
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <span className="text-xs text-muted-foreground">每行一条测试消息</span>
                    <Button onClick={runSimulation} disabled={simulation.isPending}>
                      {simulation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                      运行仿真
                    </Button>
                  </div>
                  {simulation.data && (
                    <div className="mt-4 border-t pt-4">
                      <div className="grid grid-cols-3 gap-3">
                        <div><div className="text-xs text-muted-foreground">样例</div><div className="mt-1 text-lg font-semibold">{simulation.data.summary.case_count}</div></div>
                        <div><div className="text-xs text-muted-foreground">自动化率</div><div className="mt-1 text-lg font-semibold">{formatPercent(simulation.data.summary.automation_rate)}</div></div>
                        <div><div className="text-xs text-muted-foreground">人工确认</div><div className="mt-1 text-lg font-semibold">{formatPercent(simulation.data.summary.hitl_rate)}</div></div>
                      </div>
                      <div className="mt-4 divide-y rounded-md border">
                        {simulation.data.cases.slice(0, 3).map((item) => (
                          <div key={item.id} className="grid grid-cols-[1fr_auto] gap-3 px-3 py-2">
                            <div className="min-w-0"><div className="truncate text-sm font-medium">{item.message}</div><div className="mt-0.5 text-xs text-muted-foreground">{item.detected_intent} · 风险 {item.risk_score}</div></div>
                            <Badge variant={item.candidate.mode === 'auto' ? 'default' : 'secondary'}>{item.candidate.mode === 'auto' ? '自动' : '确认'}</Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </section>
          </TabsContent>

          <TabsContent value="operations" className="mt-4">
            <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-lg border bg-background">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <div><h2 className="font-semibold">真实运营数据</h2><p className="mt-0.5 text-xs text-muted-foreground">最近 Agent 运行与行动闭环</p></div>
                  <Badge variant="outline">近 30 天</Badge>
                </div>
                <div className="grid grid-cols-4 border-b text-center">
                  {[
                    ['完成', overview.data?.agent.completed ?? 0],
                    ['失败', overview.data?.agent.failed ?? 0],
                    ['采纳', overview.data?.actions.accepted ?? 0],
                    ['忽略', overview.data?.actions.ignored ?? 0],
                  ].map(([label, value]) => <div key={String(label)} className="border-r px-2 py-3 last:border-r-0"><div className="text-lg font-semibold">{value}</div><div className="text-xs text-muted-foreground">{label}</div></div>)}
                </div>
                <div className="divide-y">
                  {(overview.data?.recent_runs ?? []).slice(0, 8).map((run) => (
                    <div key={run.id || run.run_id} className="flex items-center gap-3 px-4 py-3">
                      <span className={cn('flex h-8 w-8 items-center justify-center rounded-md', statusTone(run.status))}><Bot className="h-4 w-4" /></span>
                      <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{run.input_summary || run.run_id || '未命名运行'}</div><div className="mt-0.5 text-xs text-muted-foreground">{run.updated_at || '时间未记录'}</div></div>
                      <Badge variant="outline">{run.status || 'unknown'}</Badge>
                    </div>
                  ))}
                  {!overview.data?.recent_runs?.length && <div className="px-4 py-10 text-center text-sm text-muted-foreground">暂无运行记录</div>}
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-lg border bg-background">
                  <div className="flex items-center gap-2 border-b px-4 py-3"><Network className="h-4 w-4 text-primary" /><h2 className="font-semibold">Context Graph</h2></div>
                  <div className="grid grid-cols-2 border-b text-center"><div className="border-r p-3"><div className="text-xl font-semibold">{overview.data?.graph.summary.node_count ?? 0}</div><div className="text-xs text-muted-foreground">实体节点</div></div><div className="p-3"><div className="text-xl font-semibold">{overview.data?.graph.summary.edge_count ?? 0}</div><div className="text-xs text-muted-foreground">业务关系</div></div></div>
                  <div className="flex flex-wrap gap-2 p-4">
                    {Object.entries(overview.data?.graph.summary.entity_counts ?? {}).slice(0, 8).map(([key, value]) => <Badge key={key} variant="secondary">{key} {value}</Badge>)}
                    {!Object.keys(overview.data?.graph.summary.entity_counts ?? {}).length && <span className="text-sm text-muted-foreground">导入客户、项目和合同后生成关系图谱。</span>}
                  </div>
                </div>
                <div className="rounded-lg border bg-background">
                  <div className="flex items-center gap-2 border-b px-4 py-3"><GitBranch className="h-4 w-4 text-primary" /><h2 className="font-semibold">自主行动策略</h2></div>
                  <div className="divide-y">
                    {AUTONOMOUS_ACTION_POLICIES.map((policy) => <div key={policy.level} className="px-4 py-3"><div className="flex items-center justify-between"><span className="text-sm font-medium">{policy.level}</span><ChevronRight className="h-4 w-4 text-muted-foreground" /></div><div className="mt-1 text-xs text-muted-foreground">{policy.scope}</div></div>)}
                  </div>
                </div>
              </div>
            </section>
          </TabsContent>

          <TabsContent value="library" className="mt-4 space-y-4">
            <section className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border bg-background px-4 py-3">
                <div className="text-sm font-semibold">P0-P3：AI 原生能力底座</div>
                <div className="mt-1 text-xs text-muted-foreground">超级场景、仿真、AOP、知识图谱与自主行动。</div>
              </div>
              <div className="rounded-lg border bg-background px-4 py-3">
                <div className="text-sm font-semibold">P4-P6：产品形态与增长闭环</div>
                <div className="mt-1 text-xs text-muted-foreground">角色首页、模板安装、Demo 空间与首周激活。</div>
              </div>
            </section>

            <section className="rounded-lg border bg-background">
              <div className="flex items-center gap-2 border-b px-4 py-3"><Library className="h-4 w-4 text-primary" /><h2 className="font-semibold">行业 Agent 模板库</h2></div>
              <div className="grid gap-px bg-border md:grid-cols-2">
                {AGENT_TEMPLATES.map((template) => (
                  <button key={template.id} type="button" className="flex items-center gap-3 bg-background px-4 py-4 text-left hover:bg-muted/40" onClick={() => triggerAI(template.aiPrompt)}>
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Bot className="h-4 w-4" /></span>
                    <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{template.title}</span><span className="mt-1 block truncate text-xs text-muted-foreground">{template.outcomeMetric}</span></span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </button>
                ))}
              </div>
            </section>

            <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-lg border bg-background">
                <div className="flex items-center justify-between border-b px-4 py-3"><h2 className="font-semibold">AI-Native 场景</h2><Badge variant="secondary">本期重点</Badge></div>
                <div className="divide-y">
                  {AI_OPERATING_CAPABILITIES.map((item) => {
                    const Icon = item.icon;
                    return <div key={item.title} className="grid grid-cols-[36px_1fr_auto] items-center gap-3 px-4 py-3"><span className="flex h-9 w-9 items-center justify-center rounded-md bg-muted"><Icon className="h-4 w-4" /></span><div className="min-w-0"><div className="flex items-center gap-2"><span className="truncate text-sm font-medium">{item.title}</span><Badge variant="outline" className="h-5 px-1.5 text-[10px]">{item.priority}</Badge></div><div className="mt-0.5 truncate text-xs text-muted-foreground">{item.owner} · {item.status === 'live' ? '已上线' : item.status === 'ready' ? '可配置' : '规划中'}</div></div><Button asChild variant="ghost" size="icon" title={`打开${item.title}`}><Link to={item.href}><ArrowRight className="h-4 w-4" /></Link></Button></div>;
                  })}
                </div>
              </div>
              <div className="rounded-lg border bg-background">
                <div className="flex items-center gap-2 border-b px-4 py-3"><Clock3 className="h-4 w-4 text-primary" /><h2 className="font-semibold">事件驱动 Agent 触发蓝图</h2></div>
                <div className="divide-y">
                  {EVENT_TRIGGER_BLUEPRINTS.map((trigger, index) => <div key={trigger} className="flex items-start gap-3 px-4 py-3"><span className="mt-0.5 text-xs font-semibold text-primary">{String(index + 1).padStart(2, '0')}</span><span className="text-sm leading-5">{trigger}</span></div>)}
                </div>
              </div>
            </section>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
