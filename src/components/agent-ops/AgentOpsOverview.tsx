import { AlertTriangle, CheckCircle2, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import type {
  AeonInspiredOpsResult,
  AgentCIResult,
  AgentEvolutionOpsResult,
  AgentImprovementProposalResult,
  MemoryHygieneResult,
} from '@/hooks/useAIOperatingSystem';

interface AgentOpsOverviewProps {
  memory?: MemoryHygieneResult;
  evolution?: AgentEvolutionOpsResult;
  aeon?: AeonInspiredOpsResult;
  proposals?: AgentImprovementProposalResult;
  ci?: AgentCIResult;
  onOpenSection: (section: 'quality' | 'releases' | 'runtime') => void;
}

function percent(value?: number) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

export function AgentOpsOverview({
  memory,
  evolution,
  aeon,
  proposals,
  ci,
  onOpenSection,
}: AgentOpsOverviewProps) {
  const effectiveCI = ci ?? proposals?.agent_ci;
  const openIssues = (evolution?.low_quality_queue.length ?? 0) + (evolution?.redteam_center.open_high ?? 0);
  const pendingProposals = proposals?.proposals.filter((item) => item.status === 'proposed').length ?? 0;
  const needsAttention = openIssues > 0 || pendingProposals > 0 || effectiveCI?.passed === false;

  return (
    <div className="space-y-4">
      <OperationalMetricStrip
        ariaLabel="Agent 运营概览"
        metrics={[
          {
            label: '运行状态',
            value: aeon?.heartbeat.status === 'ok' ? '正常' : '需检查',
            tone: aeon?.heartbeat.status === 'ok' ? 'success' : 'warning',
          },
          {
            label: '质量门禁',
            value: percent(effectiveCI?.score),
            tone: effectiveCI?.passed ? 'success' : 'warning',
          },
          {
            label: '记忆健康',
            value: memory?.hygiene_score ?? 0,
            detail: '满分 100',
          },
          {
            label: '待处理问题',
            value: openIssues,
            tone: openIssues > 0 ? 'danger' : 'default',
          },
          {
            label: '待审批改进',
            value: pendingProposals,
            tone: pendingProposals > 0 ? 'warning' : 'default',
          },
        ]}
      />

      <section className="border-y bg-card/45">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold">需要处理</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">只显示会影响质量、发布或客户信任的事项。</p>
          </div>
          <Badge variant={needsAttention ? 'destructive' : 'secondary'}>
            {needsAttention ? '需要关注' : '运行稳定'}
          </Badge>
        </div>

        {!needsAttention ? (
          <div className="flex items-center gap-2 px-4 py-5 text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4 text-emerald-700 dark:text-emerald-300" />
            当前没有阻断发布或需要人工介入的问题。
          </div>
        ) : (
          <div className="divide-y">
            {effectiveCI?.passed === false && (
              <button
                type="button"
                onClick={() => onOpenSection('releases')}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/25"
              >
                <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">质量门禁未通过</span>
                  <span className="block truncate text-xs text-muted-foreground">{effectiveCI.recommendation}</span>
                </span>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </button>
            )}
            {openIssues > 0 && (
              <button
                type="button"
                onClick={() => onOpenSection('quality')}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/25"
              >
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-300" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">发现 {openIssues} 个质量或安全问题</span>
                  <span className="block text-xs text-muted-foreground">查看低质量样本与红队发现。</span>
                </span>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </button>
            )}
            {pendingProposals > 0 && (
              <button
                type="button"
                onClick={() => onOpenSection('releases')}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/25"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{pendingProposals} 项改进等待人工决策</span>
                  <span className="block text-xs text-muted-foreground">Agent 不会绕过审批自动修改生产行为。</span>
                </span>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </button>
            )}
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <section className="border-y bg-card/45">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h2 className="text-sm font-semibold">关键技能健康度</h2>
            <Button variant="ghost" size="sm" onClick={() => onOpenSection('runtime')}>查看运行时</Button>
          </div>
          <div className="divide-y">
            {(aeon?.skill_health ?? []).slice(0, 4).map((skill) => (
              <div key={skill.skill} className="grid grid-cols-[minmax(0,1fr)_80px_64px] items-center gap-3 px-4 py-2.5 text-xs">
                <span className="truncate font-medium">{skill.skill}</span>
                <span className="text-right tabular-nums text-muted-foreground">{percent(skill.success_rate)}</span>
                <Badge variant={skill.score >= 4 ? 'secondary' : 'destructive'} className="justify-center">
                  {skill.score}/5
                </Badge>
              </div>
            ))}
            {!aeon?.skill_health?.length && (
              <div className="px-4 py-5 text-sm text-muted-foreground">等待首次技能健康检查。</div>
            )}
          </div>
        </section>

        <section className="border-y bg-card/45 px-4 py-3">
          <h2 className="text-sm font-semibold">客户可见信任摘要</h2>
          <div className="mt-3 text-3xl font-semibold tabular-nums">
            {evolution?.trust_center.confidence_score ?? 0}
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            {evolution?.trust_center.audit_story ?? '等待生成本周 Agent 行为与审计摘要。'}
          </p>
        </section>
      </div>
    </div>
  );
}

