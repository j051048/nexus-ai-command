import { AlertTriangle, CheckCircle2, Library, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { OperationalMetricStrip } from '@/components/common/OperationalMetricStrip';
import type {
  AgentEvolutionOpsResult,
  MemoryHygieneResult,
  PromptManifest,
} from '@/hooks/useAIOperatingSystem';

interface AgentOpsQualityProps {
  registry: PromptManifest[];
  memory?: MemoryHygieneResult;
  evolution?: AgentEvolutionOpsResult;
}

export function AgentOpsQuality({ registry, memory, evolution }: AgentOpsQualityProps) {
  return (
    <div className="space-y-4">
      <OperationalMetricStrip
        ariaLabel="Agent 质量指标"
        metrics={[
          { label: '提示词清单', value: registry.length },
          { label: '过期记忆', value: memory?.expired_memories ?? 0, tone: memory?.expired_memories ? 'warning' : 'default' },
          { label: '冲突候选', value: memory?.conflict_candidates ?? 0, tone: memory?.conflict_candidates ? 'warning' : 'default' },
          { label: '评测样本', value: evolution?.eval_dataset.case_count ?? 0 },
          { label: '高危红队发现', value: evolution?.redteam_center.open_high ?? 0, tone: evolution?.redteam_center.open_high ? 'danger' : 'default' },
        ]}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="border-y bg-card/45">
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <Library className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">提示词版本与责任人</h2>
          </div>
          <div className="max-h-80 divide-y overflow-y-auto">
            {registry.map((manifest) => (
              <div key={manifest.prompt_version} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{manifest.agent_code}</div>
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">{manifest.scenario}</div>
                </div>
                <div className="text-right">
                  <Badge variant="outline">{manifest.prompt_version}</Badge>
                  <div className="mt-1 text-[11px] text-muted-foreground">{manifest.owner}</div>
                </div>
              </div>
            ))}
            {!registry.length && <div className="px-4 py-5 text-sm text-muted-foreground">暂无提示词版本数据。</div>}
          </div>
        </section>

        <section className="border-y bg-card/45">
          <div className="flex items-center gap-2 border-b px-4 py-3">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">Context 与记忆卫生</h2>
          </div>
          <div className="divide-y">
            {(memory?.recommendations ?? []).slice(0, 5).map((item) => (
              <div key={item} className="flex gap-2 px-4 py-3 text-sm leading-5">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-300" />
                <span>{item}</span>
              </div>
            ))}
            {!memory?.recommendations?.length && (
              <div className="px-4 py-5 text-sm text-muted-foreground">当前没有记忆卫生建议。</div>
            )}
          </div>
        </section>
      </div>

      <section className="border-y bg-card/45">
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-amber-700 dark:text-amber-300" />
          <h2 className="text-sm font-semibold">失败样本与红队发现</h2>
        </div>
        <div className="divide-y">
          {(evolution?.low_quality_queue ?? []).slice(0, 8).map((item) => (
            <div key={item.id} className="grid gap-2 px-4 py-3 md:grid-cols-[100px_minmax(0,1fr)_auto] md:items-center">
              <Badge variant={item.priority === 'high' ? 'destructive' : 'secondary'} className="w-fit">{item.priority}</Badge>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{item.reason}</div>
                <div className="mt-0.5 truncate text-xs text-muted-foreground">{item.suggested_action}</div>
              </div>
              <span className="text-[11px] text-muted-foreground">{item.source}</span>
            </div>
          ))}
          {!evolution?.low_quality_queue?.length && (
            <div className="flex items-center gap-2 px-4 py-5 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-700 dark:text-emerald-300" />
              当前没有进入人工复核队列的低质量样本。
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

