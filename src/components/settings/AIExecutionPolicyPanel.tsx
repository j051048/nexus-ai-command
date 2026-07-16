import { Check, CircleDollarSign, Clock3, Loader2, ShieldCheck, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  type AIExecutionMode,
  useAIExecutionPolicy,
  useUpdateAIExecutionPolicy,
} from '@/hooks/useAIExecutionPolicy';
import { cn } from '@/lib/utils';

const MODES: Array<{
  value: AIExecutionMode;
  label: string;
  summary: string;
  detail: string;
}> = [
  {
    value: 'economy',
    label: '省成本',
    summary: '一次完成',
    detail: '适合查询、摘要和日常问答',
  },
  {
    value: 'balanced',
    label: '智能平衡',
    summary: '按风险校验',
    detail: '推荐。复杂任务自动增加一次校验',
  },
  {
    value: 'strict',
    label: '严谨优先',
    summary: '高风险复核',
    detail: '适合审批、合同和关键经营决策',
  },
];

export function AIExecutionPolicyPanel() {
  const { data, isLoading } = useAIExecutionPolicy();
  const updatePolicy = useUpdateAIExecutionPolicy();
  const [mode, setMode] = useState<AIExecutionMode>('balanced');

  useEffect(() => {
    if (data?.policy.mode) setMode(data.policy.mode);
  }, [data?.policy.mode]);

  if (isLoading || !data) {
    return <Skeleton className="h-[360px] w-full" />;
  }

  const preview = data.presets[mode];
  const isDirty = mode !== data.policy.mode;

  const save = async () => {
    try {
      await updatePolicy.mutateAsync({ mode });
      toast.success('AI 执行方式已更新');
    } catch {
      toast.error('执行方式保存失败，请稍后重试');
    }
  };

  return (
    <Card className="max-w-3xl border-border shadow-sm">
      <CardHeader className="border-b border-border pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">AI 执行方式</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              系统自动判断任务难度，不需要为每个场景选择模型。
            </p>
          </div>
          <Badge variant="outline" className="font-normal">
            生产模型 · {data.policy.primary_model}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-5">
        <div className="grid overflow-hidden rounded-md border border-border sm:grid-cols-3">
          {MODES.map((item) => {
            const selected = item.value === mode;
            return (
              <button
                key={item.value}
                type="button"
                aria-pressed={selected}
                onClick={() => setMode(item.value)}
                className={cn(
                  'min-h-28 border-b border-border px-4 py-4 text-left transition-colors last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0',
                  selected ? 'bg-primary/[0.06]' : 'bg-background hover:bg-muted/50',
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{item.label}</span>
                  {selected && <Check className="h-4 w-4 text-primary" />}
                </span>
                <span className="mt-2 block text-sm text-foreground">{item.summary}</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  {item.detail}
                </span>
              </button>
            );
          })}
        </div>

        <div className="grid gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-3">
          <div className="bg-background p-4">
            <Zap className="mb-3 h-4 w-4 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">最多调用</p>
            <p className="mt-1 text-lg font-semibold">{preview.max_calls} 次</p>
          </div>
          <div className="bg-background p-4">
            <Clock3 className="mb-3 h-4 w-4 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">任务时限</p>
            <p className="mt-1 text-lg font-semibold">{preview.max_latency_ms / 1000} 秒</p>
          </div>
          <div className="bg-background p-4">
            <CircleDollarSign className="mb-3 h-4 w-4 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">单任务成本上限</p>
            <p className="mt-1 text-lg font-semibold">${preview.max_task_cost_usd}</p>
          </div>
        </div>

        <div className="flex items-start gap-3 rounded-md bg-muted/45 px-4 py-3">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" />
          <div className="text-sm">
            <p className="font-medium">成本保护已开启</p>
            <p className="mt-1 text-muted-foreground">
              定时任务仅使用主模型；高价模型不会被自动调用；每次运行都会保留可审计凭证。
            </p>
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={save} disabled={!isDirty || updatePolicy.isPending}>
            {updatePolicy.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            保存执行方式
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
