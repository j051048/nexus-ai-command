import { Activity, Play, TimerReset } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import type { AeonInspiredOpsResult, AgentEvolutionOpsResult } from '@/hooks/useAIOperatingSystem';

interface AgentOpsRuntimeProps {
  aeon?: AeonInspiredOpsResult;
  evolution?: AgentEvolutionOpsResult;
  isRunningHeartbeat: boolean;
  isRegisteringSchedule: boolean;
  onRunHeartbeat: () => void;
  onRegisterSchedule: () => void;
}

function percent(value?: number) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

export function AgentOpsRuntime({
  aeon,
  evolution,
  isRunningHeartbeat,
  isRegisteringSchedule,
  onRunHeartbeat,
  onRegisterSchedule,
}: AgentOpsRuntimeProps) {
  const runtimeGroups = [
    { label: '事件触发器', value: aeon?.reactive_triggers.trigger_count ?? 0, detail: `已触发 ${aeon?.reactive_triggers.fired.length ?? 0}` },
    { label: '修复提案', value: aeon?.self_repair.proposal_count ?? 0, detail: '禁止自动应用' },
    { label: '技能链', value: aeon?.skill_chains.chain_count ?? 0, detail: aeon?.skill_chains.chains?.[0]?.id },
    { label: '运行记忆', value: aeon?.operating_memory.run_count ?? 0, detail: `${aeon?.operating_memory.event_count ?? 0} 事件` },
    { label: '实例', value: aeon?.instance_fleet.instances.length ?? 0, detail: '受控运行' },
  ];

  return (
    <div className="space-y-4">
      <section className="border-y bg-card/45">
        <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <Activity className="mt-0.5 h-4 w-4 text-primary" />
            <div>
              <h2 className="text-sm font-semibold">运行时监督</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">巡检技能健康、事件触发、运行记忆与外部能力边界。</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={onRunHeartbeat} disabled={isRunningHeartbeat}>
              <Play className="mr-1.5 h-4 w-4" />
              {isRunningHeartbeat ? '巡检中' : '立即巡检'}
            </Button>
            <Button size="sm" variant="outline" onClick={onRegisterSchedule} disabled={isRegisteringSchedule}>
              <TimerReset className="mr-1.5 h-4 w-4" />
              每日巡检
            </Button>
          </div>
        </div>
        <div className="px-4 py-3">
          <div className="flex items-center gap-2">
            <Badge variant={aeon?.heartbeat.status === 'ok' ? 'secondary' : 'destructive'}>
              {aeon?.heartbeat.status === 'ok' ? '运行正常' : '需要关注'}
            </Badge>
            <span className="text-xs text-muted-foreground">{aeon?.heartbeat.summary ?? '等待首次运行时巡检。'}</span>
          </div>
        </div>
      </section>

      <OperationalMetricStrip metrics={runtimeGroups} ariaLabel="Agent 运行时指标" />

      <section className="border-y bg-card/45">
        <div className="border-b px-4 py-3">
          <h2 className="text-sm font-semibold">技能健康</h2>
        </div>
        <div className="divide-y">
          {(aeon?.skill_health ?? []).map((skill) => (
            <div key={skill.skill} className="grid gap-2 px-4 py-3 md:grid-cols-[minmax(0,1fr)_90px_80px_100px] md:items-center">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{skill.skill}</div>
                <div className="mt-0.5 truncate text-xs text-muted-foreground">{skill.recommended_action}</div>
              </div>
              <span className="text-xs tabular-nums text-muted-foreground">成功 {percent(skill.success_rate)}</span>
              <span className="text-xs tabular-nums text-muted-foreground">失败 {skill.failure_count}</span>
              <Badge variant={skill.score >= 4 ? 'outline' : 'destructive'} className="justify-center">{skill.score}/5</Badge>
            </div>
          ))}
          {!aeon?.skill_health?.length && <div className="px-4 py-5 text-sm text-muted-foreground">暂无技能健康数据。</div>}
        </div>
      </section>

      <details className="border-y bg-card/45">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">高级运行时能力</summary>
        <div className="grid gap-0 border-t md:grid-cols-2">
          <div className="border-b px-4 py-3 md:border-r">
            <div className="text-xs font-medium">多 Agent 协作协议</div>
            <div className="mt-1 text-xs text-muted-foreground">{evolution?.multi_agent_protocol.name ?? '等待加载'}</div>
          </div>
          <div className="border-b px-4 py-3">
            <div className="text-xs font-medium">外部能力边界</div>
            <div className="mt-1 text-xs text-muted-foreground">{aeon?.external_capabilities.auth_boundary ?? '等待加载'}</div>
          </div>
          <div className="border-b px-4 py-3 md:border-b-0 md:border-r">
            <div className="text-xs font-medium">角色风格契约</div>
            <div className="mt-1 text-xs text-muted-foreground">{aeon?.persona_soul.style_contract ?? '等待加载'}</div>
          </div>
          <div className="px-4 py-3">
            <div className="text-xs font-medium">运行焦点</div>
            <div className="mt-1 text-xs text-muted-foreground">{aeon?.universal_var.routing_hint ?? '等待加载'}</div>
          </div>
        </div>
      </details>
    </div>
  );
}

