import {
  useAgentCI,
  useAeonInspiredOps,
  useAgentEvolutionOps,
  useAgentImprovementProposals,
  useDecideAgentProposal,
  useMemoryHygiene,
  usePromptRegistry,
  useRunAeonInspiredHeartbeat,
} from '@/hooks/useAIOperatingSystem';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  BrainCircuit,
  CheckCircle2,
  GitCompareArrows,
  Library,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

function formatPercent(value?: number) {
  if (typeof value !== 'number') return '0%';
  return `${Math.round(value * 100)}%`;
}

export default function AgentImprovementCenterPage() {
  const registry = usePromptRegistry();
  const proposals = useAgentImprovementProposals();
  const memory = useMemoryHygiene();
  const evolutionOps = useAgentEvolutionOps();
  const aeonOps = useAeonInspiredOps('scientific instrument sales');
  const runAeonHeartbeat = useRunAeonInspiredHeartbeat();
  const decideProposal = useDecideAgentProposal();
  const agentCI = useAgentCI();

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      <section className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <BrainCircuit className="h-4 w-4" />
              Agent Improvement Center
            </div>
            <h1 className="text-2xl font-bold tracking-tight">内置 Agent 自我进化控制台</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              这里把提示词工程、Context 工程、Harness 工程和 Hermes 式改进提案放在同一张运营台上：Agent 可以提出改进，但不能绕过 CI、灰度和人工批准。
            </p>
          </div>
          <Button
            onClick={() =>
              agentCI.mutate({
                candidate_metadata: { source: 'operator_button', estimated_tokens: 3200 },
              })
            }
            disabled={agentCI.isPending}
          >
            <GitCompareArrows className="mr-2 h-4 w-4" />
            运行 Agent CI
          </Button>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="text-sm font-semibold text-primary">Boss View</div>
          <h2 className="mt-1 text-lg font-semibold">AI value, risk, and weekly operating story</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Boss users should see value, saved hours, confidence, risk exceptions, and what needs approval.
            Deep prompt, eval, and repair internals stay below in Admin Control Plane.
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="text-sm font-semibold text-primary">Admin Control Plane</div>
          <h2 className="mt-1 text-lg font-semibold">Health, triggers, evals, repair, and release gates</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Admin users operate heartbeat snapshots, skill health, reactive triggers, red-team findings,
            self-repair proposals, gray release, and rollback.
          </p>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Library className="h-4 w-4 text-primary" />
            <h2 className="font-semibold">Prompt Registry</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            每个 Agent 都要有 prompt_version、owner、risk tier 和上线前必须通过的 eval gates。
          </p>
          <div className="mt-3 space-y-3">
            {(registry.data ?? []).map((manifest) => (
              <div key={manifest.prompt_version} className="rounded-md border bg-background/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{manifest.agent_code}</span>
                  <Badge variant="outline">{manifest.prompt_version}</Badge>
                </div>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{manifest.scenario}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {manifest.eval_gates.map((gate) => (
                    <span key={gate} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                      {gate}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {!registry.data?.length && (
              <div className="rounded-md border bg-background/60 p-3 text-sm text-muted-foreground">
                Prompt Registry 暂无可用数据，请确认后端 `/prompt-registry` 可访问。
              </div>
            )}
          </div>
        </section>

        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <h2 className="font-semibold">Context Quality & Memory Hygiene</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Context 不再只是 token 拼接，而是带相关度、来源可信度、时效性、权限范围和证据包。
          </p>
          <div className="mt-3 grid gap-3">
            <div className="rounded-md border bg-background/60 p-3">
              <div className="text-xs text-muted-foreground">Memory Hygiene Score</div>
              <div className="mt-2 text-2xl font-semibold">{memory.data?.hygiene_score ?? 0}</div>
              <p className="mt-1 text-xs text-muted-foreground">
                过期 {memory.data?.expired_memories ?? 0}，冲突候选 {memory.data?.conflict_candidates ?? 0}，Golden Examples {memory.data?.golden_examples ?? 0}
              </p>
            </div>
            {(memory.data?.recommendations ?? []).slice(0, 3).map((item) => (
              <div key={item} className="flex gap-2 rounded-md border bg-background/60 p-3 text-sm leading-5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <GitCompareArrows className="h-4 w-4 text-primary" />
            <h2 className="font-semibold">Agent CI / Replay Harness</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            每次 prompt、context、tool 或 SOP 规则改动，都必须先跑 deterministic replay 和行为 diff。
          </p>
          <div className="mt-3 rounded-md border bg-background/60 p-3">
            <div className="text-xs text-muted-foreground">最近 CI 结果</div>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-2xl font-semibold">
                {formatPercent(agentCI.data?.score ?? proposals.data?.agent_ci.score)}
              </span>
              <Badge variant={agentCI.data?.passed || proposals.data?.agent_ci.passed ? 'default' : 'secondary'}>
                {agentCI.data?.recommendation ?? proposals.data?.agent_ci.recommendation ?? '等待运行'}
              </Badge>
            </div>
            <div className="mt-3 space-y-2">
              {(agentCI.data?.cases ?? proposals.data?.agent_ci.cases ?? []).slice(0, 3).map((item) => (
                <div key={item.id} className="rounded-md border bg-card px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span>{item.id}</span>
                    <Badge variant={item.passed ? 'default' : 'destructive'}>{item.passed ? 'pass' : 'fail'}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </section>

      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Hermes 式改进提案</h2>
        </div>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Agent 可以从失败、低质量上下文和高采纳样例里提出改进，但默认 self_mutation_allowed=false。
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(proposals.data?.proposals ?? []).map((proposal) => (
            <div key={proposal.id} className="rounded-lg border bg-background/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge variant="outline">{proposal.category}</Badge>
                <Badge variant={proposal.risk_level === 'high' ? 'destructive' : 'secondary'}>
                  {proposal.risk_level}
                </Badge>
              </div>
              <h3 className="mt-3 font-semibold">{proposal.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{proposal.rationale}</p>
              <p className="mt-3 text-xs text-muted-foreground">
                状态：{proposal.status}；人工批准：{proposal.approval_required ? '必须' : '可选'}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(proposals.data?.governance.required_flow ?? []).map((step) => (
            <span key={step} className="rounded-full border px-3 py-1 text-xs text-muted-foreground">
              {step}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">10项 Agent Evolution Ops</h2>
        </div>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          把 Agent 从“能运行”推进到“可运营”：真实持久化、人工审批、灰度回滚、Diff、低质队列、评测集、业务奖励模型、技能市场、多 Agent 协议、红队和客户可见信任中心。
        </p>

        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">1. DB Persistence</div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              Migration: {evolutionOps.data?.persistence.migration ?? '20260525_agent_evolution_ops.sql'}
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {(evolutionOps.data?.persistence.tables ?? []).slice(0, 6).map((table) => (
                <Badge key={table} variant="outline">
                  {table}
                </Badge>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">2. Approval / Gray / Rollback</div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              所有提案默认 proposed，只有人工审批后才能进入 gray_release 或 rollback。
            </p>
            <div className="mt-3 space-y-2">
              {(evolutionOps.data?.proposal_flow.records ?? []).slice(0, 2).map((item) => (
                <div key={item.id} className="rounded-md border bg-card p-2">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-medium">{item.title}</span>
                    <Badge variant="secondary">{item.status}</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        decideProposal.mutate({
                          proposal_key: item.id,
                          action: 'gray_release',
                          gray_percentage: 10,
                          reviewer_note: 'Operator starts 10% gray release from Agent Evolution Ops.',
                        })
                      }
                      disabled={decideProposal.isPending}
                    >
                      10%灰度
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        decideProposal.mutate({
                          proposal_key: item.id,
                          action: 'rollback',
                          reviewer_note: 'Operator rollback from Agent Evolution Ops.',
                        })
                      }
                      disabled={decideProposal.isPending}
                    >
                      回滚
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">3. Prompt / Context / Tool Diff</div>
            <div className="mt-2 space-y-2 text-xs text-muted-foreground">
              {Object.entries(evolutionOps.data?.diffs ?? {}).map(([name, value]) => (
                <div key={name} className="rounded-md border bg-card p-2">
                  <div className="font-medium text-foreground">{name}</div>
                  <div className="mt-1 line-clamp-3 break-words">{JSON.stringify(value)}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">4. Low Quality Queue</div>
            <div className="mt-3 space-y-2">
              {(evolutionOps.data?.low_quality_queue ?? []).slice(0, 3).map((item) => (
                <div key={item.id} className="rounded-md border bg-card p-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span>{item.id}</span>
                    <Badge variant={item.priority === 'high' ? 'destructive' : 'secondary'}>{item.priority}</Badge>
                  </div>
                  <p className="mt-1 line-clamp-2 text-muted-foreground">{item.reason}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">5. Eval Dataset Manager</div>
            <div className="mt-2 text-2xl font-semibold">{evolutionOps.data?.eval_dataset.case_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              from real runs: {evolutionOps.data?.eval_dataset.from_real_runs ?? 0}
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {(evolutionOps.data?.eval_dataset.coverage_dimensions ?? []).map((dimension) => (
                <Badge key={dimension} variant="outline">
                  {dimension}
                </Badge>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">6. Business Reward Model</div>
            <div className="mt-2 text-2xl font-semibold">{formatPercent(evolutionOps.data?.reward_model.score)}</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {(evolutionOps.data?.reward_model.signals ?? []).map((signal) => (
                <Badge key={signal.name} variant="outline">
                  {signal.name}: {signal.weight}
                </Badge>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">7. Agent Skill Marketplace</div>
            <div className="mt-3 space-y-2">
              {(evolutionOps.data?.skill_marketplace ?? []).slice(0, 4).map((skill) => (
                <div key={skill.id} className="rounded-md border bg-card p-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{skill.name}</span>
                    <Badge variant="secondary">{skill.install_state}</Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground">{skill.scenario}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">8. Multi-Agent Protocol</div>
            <p className="mt-1 text-xs text-muted-foreground">
              {evolutionOps.data?.multi_agent_protocol.name ?? 'Nexus Agent Collaboration Protocol'}
            </p>
            <div className="mt-3 space-y-2">
              {(evolutionOps.data?.multi_agent_protocol.flows ?? []).map((flow) => (
                <div key={flow.id} className="rounded-md border bg-card p-2 text-xs">
                  <div className="font-medium">{flow.id}</div>
                  <div className="mt-1 text-muted-foreground">{flow.steps.map((step) => step.agent).join(' -> ')}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">9. Red Team Center</div>
            <div className="mt-2 flex items-end gap-2">
              <span className="text-2xl font-semibold">{evolutionOps.data?.redteam_center.scenario_count ?? 0}</span>
              <Badge variant={(evolutionOps.data?.redteam_center.open_high ?? 0) > 0 ? 'destructive' : 'default'}>
                open high: {evolutionOps.data?.redteam_center.open_high ?? 0}
              </Badge>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {evolutionOps.data?.redteam_center.required_release_gate}
            </p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4 lg:col-span-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-semibold">10. Customer Visible Trust Center</div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {evolutionOps.data?.trust_center.audit_story ?? 'Waiting for trust report.'}
                </p>
              </div>
              <Badge variant="default">
                confidence {evolutionOps.data?.trust_center.confidence_score ?? 0}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(evolutionOps.data?.trust_center.controls ?? []).map((control) => (
                <span key={control} className="rounded-full border px-3 py-1 text-xs text-muted-foreground">
                  {control}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-primary" />
          <h2 className="font-semibold">Aeon-style Agent Ops Runtime</h2>
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => runAeonHeartbeat.mutate('scientific instrument sales')}
            disabled={runAeonHeartbeat.isPending}
          >
            Run heartbeat
          </Button>
        </div>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Learned from Aeon: unattended heartbeat, skill health, reactive triggers, governed self-repair,
          skill chains, universal var, operating memory, agent fleet, persona/soul, and MCP/A2A exposure.
        </p>

        <div className="mt-4 grid gap-3 lg:grid-cols-5">
          <div className="rounded-lg border bg-background/60 p-4 lg:col-span-2">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold">1. Heartbeat Supervisor</div>
              <Badge variant={aeonOps.data?.heartbeat.status === 'ok' ? 'default' : 'destructive'}>
                {aeonOps.data?.heartbeat.status ?? 'loading'}
              </Badge>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {aeonOps.data?.heartbeat.summary ?? 'Waiting for heartbeat summary.'}
            </p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4 lg:col-span-3">
            <div className="text-sm font-semibold">2. Skill Health</div>
            <div className="mt-3 grid gap-2 md:grid-cols-3">
              {(aeonOps.data?.skill_health ?? []).slice(0, 3).map((skill) => (
                <div key={skill.skill} className="rounded-md border bg-card p-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{skill.skill}</span>
                    <Badge variant={skill.score >= 4 ? 'default' : skill.score >= 3 ? 'secondary' : 'destructive'}>
                      {skill.score}/5
                    </Badge>
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    success {formatPercent(skill.success_rate)} · failures {skill.failure_count}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">3. Reactive Triggers</div>
            <div className="mt-2 text-2xl font-semibold">{aeonOps.data?.reactive_triggers.trigger_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">fired: {aeonOps.data?.reactive_triggers.fired.length ?? 0}</p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">4. Self Repair</div>
            <div className="mt-2 text-2xl font-semibold">{aeonOps.data?.self_repair.proposal_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              auto apply: {aeonOps.data?.self_repair.auto_apply ? 'yes' : 'no'}
            </p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">5. Skill Chains</div>
            <div className="mt-2 text-2xl font-semibold">{aeonOps.data?.skill_chains.chain_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">{aeonOps.data?.skill_chains.chains?.[0]?.id}</p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">6. Universal var</div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {aeonOps.data?.universal_var.routing_hint ?? 'Focus parameter will bias retrieval and chain output.'}
            </p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4">
            <div className="text-sm font-semibold">7. Operating Memory</div>
            <div className="mt-2 text-2xl font-semibold">{aeonOps.data?.operating_memory.stores.length ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              runs {aeonOps.data?.operating_memory.run_count ?? 0} · events {aeonOps.data?.operating_memory.event_count ?? 0}
            </p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4 lg:col-span-2">
            <div className="text-sm font-semibold">8. Instance Fleet</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {(aeonOps.data?.instance_fleet.instances ?? []).map((instance) => (
                <Badge key={String(instance.id)} variant="outline">
                  {String(instance.id)}
                </Badge>
              ))}
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-4 lg:col-span-2">
            <div className="text-sm font-semibold">9. Persona / Soul</div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {aeonOps.data?.persona_soul.style_contract ?? 'Role style packs keep output consistent.'}
            </p>
          </div>

          <div className="rounded-lg border bg-background/60 p-4 lg:col-span-3">
            <div className="text-sm font-semibold">10. MCP / A2A Capabilities</div>
            <div className="mt-2 flex flex-wrap gap-1">
              {(aeonOps.data?.external_capabilities.capabilities ?? []).map((capability) => (
                <Badge key={String(capability.name)} variant="outline">
                  {String(capability.name)}
                </Badge>
              ))}
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {aeonOps.data?.external_capabilities.auth_boundary}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
