import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCheck2,
  RefreshCw,
  Trophy,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useArtifactQualityOps } from '@/hooks/useArtifactQualityOps';
import { cn } from '@/lib/utils';

const FAILURE_LABELS: Record<string, string> = {
  evidence_insufficient: '证据覆盖不足',
  character_count_below_minimum: '正文篇幅不足',
  missing_required_section: '必需章节缺失',
  unsupported_claim: '存在无来源结论',
  semantic_quality_below_threshold: '语义审校未通过',
};

function percent(value: number | undefined) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

export default function ArtifactQualityOperationsPage() {
  const [days, setDays] = useState(30);
  const query = useArtifactQualityOps(days);
  const data = query.data;

  const metrics = [
    {
      label: '一次通过率',
      value: percent(data?.slo.metrics.ready_rate),
      note: '目标 90%',
      icon: FileCheck2,
    },
    {
      label: '证据覆盖',
      value: `${Math.round(data?.slo.metrics.avg_evidence_coverage || 0)}%`,
      note: '目标 90%',
      icon: CheckCircle2,
    },
    {
      label: '下载采用率',
      value: percent(data?.value.adoption_rate),
      note: `${data?.value.unique_artifacts || 0} 份成果`,
      icon: Download,
    },
    {
      label: '赢单回流',
      value: String(data?.value.won_count || 0),
      note: '已关联业务结果',
      icon: Trophy,
    },
  ];

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium text-primary">AI 交付运营</p>
          <h1 className="mt-2 text-2xl font-semibold">成果质量运营</h1>
          <p className="mt-1 text-sm text-muted-foreground">从资料入库、生成执行到下载采用，查看 AI 成果是否真正可交付。</p>
        </div>
        <div className="flex items-center gap-2">
            <select
              aria-label="统计周期"
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="h-9 rounded-md border bg-background px-3 text-sm"
            >
              <option value={7}>近 7 天</option>
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
            </select>
            <Button variant="outline" size="icon" onClick={() => void query.refetch()} title="刷新">
              <RefreshCw className={cn('h-4 w-4', query.isFetching && 'animate-spin')} />
            </Button>
        </div>
      </header>

      {query.isError && (
        <div className="mt-6 flex items-center gap-2 border-y py-4 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4" />质量数据暂时不可用，请检查数据库迁移与任务队列。
        </div>
      )}

      <section className="mt-6 grid border-y sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map(({ label, value, note, icon: Icon }, index) => (
          <div key={label} className={cn('px-5 py-5', index > 0 && 'border-t sm:border-l sm:border-t-0')}>
            <div className="flex items-center gap-2 text-xs text-muted-foreground"><Icon className="h-4 w-4" />{label}</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
            <p className="mt-1 text-xs text-muted-foreground">{note}</p>
          </div>
        ))}
      </section>

      <section className="mt-8 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="mb-3 flex items-end justify-between border-b pb-3">
            <div><h2 className="font-semibold">返工原因</h2><p className="mt-1 text-xs text-muted-foreground">按质量门失败次数排序</p></div>
            <span className="text-xs text-muted-foreground">{data?.failures.sample_size || 0} 次审校</span>
          </div>
          <div className="divide-y">
            {(data?.failures.failure_modes || []).slice(0, 8).map((item) => (
              <div key={item.code} className="grid grid-cols-[1fr_auto_auto] items-center gap-4 py-3 text-sm">
                <span>{FAILURE_LABELS[item.code] || item.code}</span>
                <span className="text-muted-foreground">{percent(item.share)}</span>
                <span className="w-8 text-right font-medium tabular-nums">{item.count}</span>
              </div>
            ))}
            {!data?.failures.failure_modes?.length && <p className="py-10 text-sm text-muted-foreground">当前周期暂无返工样本。</p>}
          </div>
        </div>

        <div>
          <div className="border-b pb-3"><h2 className="font-semibold">生产链路</h2><p className="mt-1 text-xs text-muted-foreground">只显示需要运营人员关注的异常</p></div>
          <dl className="divide-y text-sm">
            <div className="flex items-center justify-between py-4"><dt>资料整理失败</dt><dd className={cn('font-medium', data?.ingestion.failed ? 'text-destructive' : 'text-emerald-700')}>{data?.ingestion.failed || 0}</dd></div>
            <div className="flex items-center justify-between py-4"><dt>资料整理中</dt><dd className="font-medium">{data?.ingestion.processing || 0}</dd></div>
            <div className="flex items-center justify-between py-4"><dt>失联资料任务</dt><dd className={cn('font-medium', data?.ingestion.stale ? 'text-destructive' : 'text-emerald-700')}>{data?.ingestion.stale || 0}</dd></div>
            <div className="flex items-center justify-between py-4"><dt>失联成果任务</dt><dd className={cn('font-medium', data?.jobs.stale_running ? 'text-destructive' : 'text-emerald-700')}>{data?.jobs.stale_running || 0}</dd></div>
            <div className="flex items-center justify-between py-4"><dt>自动接管次数</dt><dd className="font-medium">{data?.jobs.recoveries || 0}</dd></div>
          </dl>
        </div>
      </section>
    </main>
  );
}
