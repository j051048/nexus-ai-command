import { ArrowRight, Check, FileCheck2, Files, Loader2, RefreshCw, Upload } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useActivationState } from '@/hooks/useActivationState';
import { useLaunchReadiness } from '@/hooks/useLaunchReadiness';
import { cn } from '@/lib/utils';

type LaunchChecklistPanelProps = { role?: string | null; compact?: boolean };

export function LaunchChecklistPanel({ compact = false }: LaunchChecklistPanelProps) {
  const { data, isLoading, isError, refetch, isFetching } = useLaunchReadiness();
  const { open } = useActivationState();
  const steps = [
    { title: '上传企业资料', done: Boolean(data?.uploaded), icon: Upload, href: '/documents' },
    { title: '确认资料与缺口', done: Boolean(data?.facts_confirmed), icon: Files, href: null },
    { title: '交付首份方案', done: Boolean(data?.artifact_ready), icon: FileCheck2, href: '/growth/solutions' },
  ];
  const current = steps.findIndex((step) => !step.done);

  return (
    <section aria-label="首次交付进度" className="border-y border-border py-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">{current === -1 ? '首份成果已就绪' : '开始第一份客户方案'}</h2>
        <Button variant="ghost" size="icon" title="刷新交付进度" aria-label="刷新交付进度"
          disabled={isFetching} onClick={() => void refetch()}>
          {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>
      {isError ? (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <span>暂时无法读取进度</span>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>重试</Button>
        </div>
      ) : isLoading || !data ? (
        <div role="status" className="h-16 animate-pulse rounded-md bg-muted" aria-label="读取交付进度" />
      ) : (
        <ol className={cn('grid gap-3', compact ? 'sm:grid-cols-3' : 'md:grid-cols-3')}>
          {steps.map((step, index) => {
            const Icon = step.done ? Check : step.icon;
            return (
              <li key={step.title} aria-current={current === index ? 'step' : undefined}
                className="flex min-w-0 items-center gap-3 border-l border-border pl-3">
                <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md',
                  step.done ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-muted text-muted-foreground')}>
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium">{step.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{step.done ? '已完成' : index === 1 && data.uploaded && !data.searchable ? '资料整理中' : '待完成'}</div>
                </div>
                {step.href ? (
                  <Button asChild variant="ghost" size="icon" className="shrink-0">
                    <Link to={step.href} aria-label={step.title} title={step.title}><ArrowRight className="h-4 w-4" /></Link>
                  </Button>
                ) : (
                  <Button variant="ghost" size="icon" className="shrink-0" onClick={open} title={step.title} aria-label={step.title}>
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

export default LaunchChecklistPanel;
