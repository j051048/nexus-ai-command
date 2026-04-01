import { Progress } from '@/components/ui/progress';

interface BatchProgressProps {
  total: number;
  completed: number;
  failed: number;
}

export function BatchProgress({ total, completed, failed }: BatchProgressProps) {
  const progress = ((completed + failed) / total) * 100;

  return (
    <div className="fixed bottom-4 right-4 glass-card p-4 rounded-xl shadow-xl w-80 z-50">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">批量处理中...</span>
        <span className="text-xs text-muted-foreground">{completed + failed}/{total}</span>
      </div>
      <Progress value={progress} className="mb-3" />
      <div className="flex gap-4 text-xs">
        <span className="text-success">成功 {completed}</span>
        <span className="text-destructive">失败 {failed}</span>
      </div>
    </div>
  );
}
