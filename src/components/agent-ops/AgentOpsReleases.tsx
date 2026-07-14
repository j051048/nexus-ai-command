import { GitCompareArrows, RotateCcw, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type {
  AgentCIResult,
  AgentEvolutionOpsResult,
  AgentImprovementProposalResult,
} from '@/hooks/useAIOperatingSystem';

interface AgentOpsReleasesProps {
  ci?: AgentCIResult;
  proposals?: AgentImprovementProposalResult;
  evolution?: AgentEvolutionOpsResult;
  isRunningCI: boolean;
  isDeciding: boolean;
  onRunCI: () => void;
  onDecision: (proposalKey: string, action: 'gray_release' | 'rollback') => void;
}

function percent(value?: number) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

export function AgentOpsReleases({
  ci,
  proposals,
  evolution,
  isRunningCI,
  isDeciding,
  onRunCI,
  onDecision,
}: AgentOpsReleasesProps) {
  const effectiveCI = ci ?? proposals?.agent_ci;

  return (
    <div className="space-y-4">
      <section className="border-y bg-card/45">
        <div className="flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold">发布质量门禁</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">重放真实样本并比较提示词、Context 和工具行为差异。</p>
          </div>
          <Button size="sm" onClick={onRunCI} disabled={isRunningCI}>
            <GitCompareArrows className="mr-1.5 h-4 w-4" />
            {isRunningCI ? '检查中' : '运行质量检查'}
          </Button>
        </div>
        <div className="grid gap-0 divide-y md:grid-cols-[220px_minmax(0,1fr)] md:divide-x md:divide-y-0">
          <div className="px-4 py-5">
            <div className="text-xs text-muted-foreground">最近得分</div>
            <div className="mt-1 text-3xl font-semibold tabular-nums">{percent(effectiveCI?.score)}</div>
            <Badge className="mt-2" variant={effectiveCI?.passed ? 'secondary' : 'destructive'}>
              {effectiveCI?.passed ? '允许进入审批' : '阻断发布'}
            </Badge>
          </div>
          <div className="max-h-64 divide-y overflow-y-auto">
            {(effectiveCI?.cases ?? []).map((item) => (
              <div key={item.id} className="grid grid-cols-[minmax(0,1fr)_72px] items-center gap-3 px-4 py-2.5 text-xs">
                <span className="truncate">{item.message || item.id}</span>
                <Badge variant={item.passed ? 'outline' : 'destructive'} className="justify-center">
                  {item.passed ? '通过' : '失败'}
                </Badge>
              </div>
            ))}
            {!effectiveCI?.cases?.length && <div className="px-4 py-5 text-sm text-muted-foreground">尚未运行质量检查。</div>}
          </div>
        </div>
      </section>

      <section className="border-y bg-card/45">
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <div>
            <h2 className="text-sm font-semibold">改进提案与人工决策</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">所有改动先审批、再灰度；生产行为禁止自动突变。</p>
          </div>
        </div>
        <div className="divide-y">
          {(proposals?.proposals ?? []).map((proposal) => {
            const flow = evolution?.proposal_flow.records.find((item) => item.id === proposal.id);
            return (
              <div key={proposal.id} className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{proposal.title}</span>
                    <Badge variant="outline">{proposal.category}</Badge>
                    <Badge variant={proposal.risk_level === 'high' ? 'destructive' : 'secondary'}>{proposal.risk_level}</Badge>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{proposal.rationale}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{flow?.status ?? proposal.status}</Badge>
                  <Button size="sm" variant="outline" disabled={isDeciding} onClick={() => onDecision(proposal.id, 'gray_release')}>
                    10% 灰度
                  </Button>
                  <Button size="icon" variant="ghost" disabled={isDeciding} onClick={() => onDecision(proposal.id, 'rollback')} aria-label="回滚提案" title="回滚">
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })}
          {!proposals?.proposals?.length && <div className="px-4 py-5 text-sm text-muted-foreground">当前没有待评审改进提案。</div>}
        </div>
      </section>

      <details className="border-y bg-card/45">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">查看 Prompt / Context / Tool 差异</summary>
        <div className="grid gap-3 border-t p-4 md:grid-cols-3">
          {Object.entries(evolution?.diffs ?? {}).map(([name, value]) => (
            <div key={name} className="min-w-0 border bg-background/55 p-3">
              <div className="text-xs font-medium">{name.replace('_diff', '')}</div>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all text-[11px] leading-5 text-muted-foreground">
                {JSON.stringify(value, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

