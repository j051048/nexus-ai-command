import { useState } from 'react';
import { Target, Plus, Trash2, Loader2, TrendingUp, Users, DollarSign, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
  useCurrentTargets,
  useAllTargets,
  useUpsertTarget,
  useDeleteTarget,
  useTargetProgress,
  type SalesTarget,
} from '@/hooks/useTargets';
import { toast } from 'sonner';

const currentMonth = new Date().toISOString().slice(0, 7);
const currentQuarter = `${new Date().getFullYear()}-Q${Math.ceil((new Date().getMonth() + 1) / 3)}`;

function ProgressCard({
  label,
  icon: Icon,
  current,
  target,
  progress,
  unit,
  color,
}: {
  label: string;
  icon: React.ElementType;
  current: number;
  target: number;
  progress: number;
  unit: string;
  color: string;
}) {
  const pct = Math.min(progress, 100);
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={cn('p-2 rounded-lg', color)}>
              <Icon className="w-4 h-4" />
            </div>
            <span className="text-sm font-medium">{label}</span>
          </div>
          <Badge variant="outline" className="text-xs">{pct.toFixed(0)}%</Badge>
        </div>
        <Progress value={pct} className="h-2 mb-2" />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>当前: {unit}{current.toLocaleString()}</span>
          <span>目标: {unit}{target.toLocaleString()}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function CurrentProgress({ period, type }: { period: string; type: 'monthly' | 'quarterly' }) {
  const { data: tp, isLoading } = useTargetProgress(period, type);

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 rounded-lg" />)}
      </div>
    );
  }

  if (!tp) {
    return (
      <div className="text-center py-8 bg-muted/10 rounded-xl border border-dashed">
        <Target className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          {type === 'monthly' ? '当月' : '当季'}尚未设定目标
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <ProgressCard
        label="营收"
        icon={DollarSign}
        current={tp.current.revenue}
        target={Number(tp.target.revenue_target)}
        progress={tp.progress.revenue}
        unit={'\u00A5'}
        color="bg-green-500/10 text-green-500"
      />
      <ProgressCard
        label="线索"
        icon={Users}
        current={tp.current.leads}
        target={Number(tp.target.leads_target)}
        progress={tp.progress.leads}
        unit=""
        color="bg-blue-500/10 text-blue-500"
      />
      <ProgressCard
        label="转化"
        icon={TrendingUp}
        current={tp.current.conversions}
        target={Number(tp.target.conversions_target)}
        progress={tp.progress.conversions}
        unit=""
        color="bg-orange-500/10 text-orange-500"
      />
      <ProgressCard
        label="赢率"
        icon={BarChart3}
        current={Math.round(tp.current.win_rate * 100)}
        target={Math.round(Number(tp.target.win_rate_target) * 100)}
        progress={tp.progress.win_rate}
        unit=""
        color="bg-purple-500/10 text-purple-500"
      />
    </div>
  );
}

export function TargetDashboard() {
  const { data: allTargets = [], isLoading } = useAllTargets();
  const upsertTarget = useUpsertTarget();
  const deleteTarget = useDeleteTarget();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    target_type: 'monthly' as 'monthly' | 'quarterly',
    target_period: currentMonth,
    revenue_target: 0,
    leads_target: 0,
    conversions_target: 0,
    win_rate_target: 0,
  });

  const handleSubmit = async () => {
    try {
      await upsertTarget.mutateAsync(form);
      toast.success('目标已保存');
      setDialogOpen(false);
      setForm({
        target_type: 'monthly',
        target_period: currentMonth,
        revenue_target: 0,
        leads_target: 0,
        conversions_target: 0,
        win_rate_target: 0,
      });
    } catch {
      toast.error('保存失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTarget.mutateAsync(id);
      toast.success('目标已删除');
    } catch {
      toast.error('删除失败');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Target className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">个人目标看板</h1>
            <p className="text-muted-foreground">设定和追踪您的销售目标</p>
          </div>
        </div>
        <Button className="gap-2" onClick={() => setDialogOpen(true)}>
          <Plus className="w-4 h-4" />
          设定目标
        </Button>
      </div>

      {/* 当月进度 */}
      <div className="space-y-2">
        <h2 className="text-lg font-semibold">当月进度</h2>
        <CurrentProgress period={currentMonth} type="monthly" />
      </div>

      {/* 当季进度 */}
      <div className="space-y-2">
        <h2 className="text-lg font-semibold">当季进度</h2>
        <CurrentProgress period={currentQuarter} type="quarterly" />
      </div>

      {/* 历史目标列表 */}
      <Card>
        <CardHeader>
          <CardTitle>历史目标</CardTitle>
          <CardDescription>所有已设定的目标记录</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-12 rounded-lg" />)}
            </div>
          ) : allTargets.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              暂无目标记录，点击上方"设定目标"开始
            </div>
          ) : (
            <div className="space-y-2">
              {allTargets.map((t: SalesTarget) => (
                <div key={t.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50">
                  <div className="flex items-center gap-4">
                    <Badge variant="outline">{t.target_type === 'monthly' ? '月度' : '季度'}</Badge>
                    <span className="font-medium">{t.target_period}</span>
                    <span className="text-sm text-muted-foreground">
                      营收: {'\u00A5'}{Number(t.revenue_target).toLocaleString()} |
                      线索: {t.leads_target} |
                      转化: {t.conversions_target}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-red-500"
                    onClick={() => handleDelete(t.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 新建/编辑目标 Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>设定销售目标</DialogTitle>
            <DialogDescription>设置月度或季度销售目标</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>目标类型</Label>
                <Select
                  value={form.target_type}
                  onValueChange={(v) => setForm({ ...form, target_type: v as 'monthly' | 'quarterly' })}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">月度目标</SelectItem>
                    <SelectItem value="quarterly">季度目标</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>目标期间</Label>
                <Input
                  value={form.target_period}
                  onChange={(e) => setForm({ ...form, target_period: e.target.value })}
                  placeholder={form.target_type === 'monthly' ? '2026-02' : '2026-Q1'}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>营收目标 (元)</Label>
                <Input
                  type="number"
                  value={form.revenue_target || ''}
                  onChange={(e) => setForm({ ...form, revenue_target: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-2">
                <Label>线索目标 (个)</Label>
                <Input
                  type="number"
                  value={form.leads_target || ''}
                  onChange={(e) => setForm({ ...form, leads_target: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>转化目标 (个)</Label>
                <Input
                  type="number"
                  value={form.conversions_target || ''}
                  onChange={(e) => setForm({ ...form, conversions_target: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-2">
                <Label>赢率目标 (0-1)</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.win_rate_target || ''}
                  onChange={(e) => setForm({ ...form, win_rate_target: Number(e.target.value) })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={handleSubmit} disabled={upsertTarget.isPending}>
              {upsertTarget.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              保存目标
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default TargetDashboard;
