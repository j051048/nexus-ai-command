import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { 
  Target, 
  Plus, 
  Calendar, 
  TrendingUp, 
  Loader2,
  Trash2,
  Edit2,
  Save,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { 
  useAllTargets, 
  useUpsertTarget, 
  useDeleteTarget,
  useTargetProgress,
  SalesTarget,
} from '@/hooks/useTargets';

interface TargetFormData {
  target_type: 'monthly' | 'quarterly';
  target_period: string;
  revenue_target: number;
  leads_target: number;
  conversions_target: number;
  win_rate_target: number;
}

const defaultFormData: TargetFormData = {
  target_type: 'monthly',
  target_period: new Date().toISOString().slice(0, 7),
  revenue_target: 100000,
  leads_target: 50,
  conversions_target: 20,
  win_rate_target: 40,
};

export function SalesTargetManager() {
  const [showDialog, setShowDialog] = useState(false);
  const [formData, setFormData] = useState<TargetFormData>(defaultFormData);
  const [editingId, setEditingId] = useState<string | null>(null);

  const { data: targets, isLoading } = useAllTargets();
  const upsertTarget = useUpsertTarget();
  const deleteTarget = useDeleteTarget();

  const currentMonth = new Date().toISOString().slice(0, 7);
  const currentQuarter = `${new Date().getFullYear()}-Q${Math.ceil((new Date().getMonth() + 1) / 3)}`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      await upsertTarget.mutateAsync(formData);
      toast.success(editingId ? '目标已更新' : '目标已创建');
      setShowDialog(false);
      setFormData(defaultFormData);
      setEditingId(null);
    } catch (error: any) {
      toast.error('操作失败: ' + error.message);
    }
  };

  const handleEdit = (target: SalesTarget) => {
    setFormData({
      target_type: target.target_type as 'monthly' | 'quarterly',
      target_period: target.target_period,
      revenue_target: Number(target.revenue_target),
      leads_target: target.leads_target,
      conversions_target: target.conversions_target,
      win_rate_target: Number(target.win_rate_target),
    });
    setEditingId(target.id);
    setShowDialog(true);
  };

  const handleDelete = async (targetId: string) => {
    if (!confirm('确定删除此目标？')) return;
    
    try {
      await deleteTarget.mutateAsync(targetId);
      toast.success('目标已删除');
    } catch (error: any) {
      toast.error('删除失败: ' + error.message);
    }
  };

  const generatePeriodOptions = () => {
    const options: string[] = [];
    const now = new Date();
    
    if (formData.target_type === 'monthly') {
      // Generate 12 months (6 past, current, 5 future)
      for (let i = -6; i <= 5; i++) {
        const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
        options.push(date.toISOString().slice(0, 7));
      }
    } else {
      // Generate 4 quarters
      const currentYear = now.getFullYear();
      for (let y = currentYear - 1; y <= currentYear + 1; y++) {
        for (let q = 1; q <= 4; q++) {
          options.push(`${y}-Q${q}`);
        }
      }
    }
    
    return options;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">销售目标管理</h2>
          <p className="text-sm text-muted-foreground mt-1">设置团队月度/季度销售目标</p>
        </div>
        <Dialog open={showDialog} onOpenChange={(open) => {
          setShowDialog(open);
          if (!open) {
            setFormData(defaultFormData);
            setEditingId(null);
          }
        }}>
          <DialogTrigger asChild>
            <Button className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              设置目标
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{editingId ? '编辑目标' : '设置新目标'}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>目标类型</Label>
                  <Select
                    value={formData.target_type}
                    onValueChange={(v) => setFormData({ 
                      ...formData, 
                      target_type: v as 'monthly' | 'quarterly',
                      target_period: v === 'monthly' ? currentMonth : currentQuarter,
                    })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="monthly">月度目标</SelectItem>
                      <SelectItem value="quarterly">季度目标</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>目标周期</Label>
                  <Select
                    value={formData.target_period}
                    onValueChange={(v) => setFormData({ ...formData, target_period: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {generatePeriodOptions().map(period => (
                        <SelectItem key={period} value={period}>
                          {period}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>收入目标 (¥)</Label>
                <Input
                  type="number"
                  value={formData.revenue_target}
                  onChange={(e) => setFormData({ ...formData, revenue_target: Number(e.target.value) })}
                  min={0}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>线索目标</Label>
                  <Input
                    type="number"
                    value={formData.leads_target}
                    onChange={(e) => setFormData({ ...formData, leads_target: Number(e.target.value) })}
                    min={0}
                  />
                </div>
                <div className="space-y-2">
                  <Label>转化目标</Label>
                  <Input
                    type="number"
                    value={formData.conversions_target}
                    onChange={(e) => setFormData({ ...formData, conversions_target: Number(e.target.value) })}
                    min={0}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>赢率目标 (%)</Label>
                <Input
                  type="number"
                  value={formData.win_rate_target}
                  onChange={(e) => setFormData({ ...formData, win_rate_target: Number(e.target.value) })}
                  min={0}
                  max={100}
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                  取消
                </Button>
                <Button type="submit" disabled={upsertTarget.isPending}>
                  {upsertTarget.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                  {editingId ? '更新目标' : '创建目标'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Current Targets Progress */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TargetProgressCard 
          period={currentMonth} 
          type="monthly" 
          label="本月目标" 
        />
        <TargetProgressCard 
          period={currentQuarter} 
          type="quarterly" 
          label="本季度目标" 
        />
      </div>

      {/* All Targets List */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <h3 className="text-lg font-semibold text-foreground mb-4">历史目标</h3>
        
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : !targets || targets.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>还没有设置任何目标</p>
          </div>
        ) : (
          <div className="space-y-3">
            {targets.map((target) => (
              <div
                key={target.id}
                className="flex items-center justify-between p-4 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "w-10 h-10 rounded-lg flex items-center justify-center",
                    target.target_type === 'monthly' ? "bg-primary/20 text-primary" : "bg-success/20 text-success"
                  )}>
                    <Calendar className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">
                      {target.target_period} {target.target_type === 'monthly' ? '月度' : '季度'}目标
                    </p>
                    <p className="text-sm text-muted-foreground">
                      收入 ¥{Number(target.revenue_target).toLocaleString()} · 
                      线索 {target.leads_target} · 
                      转化 {target.conversions_target}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" onClick={() => handleEdit(target)}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={() => handleDelete(target.id)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Target Progress Card Component
function TargetProgressCard({ 
  period, 
  type, 
  label 
}: { 
  period: string; 
  type: 'monthly' | 'quarterly';
  label: string;
}) {
  const { data: progress, isLoading } = useTargetProgress(period, type);

  if (isLoading) {
    return (
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!progress) {
    return (
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center">
            <Target className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground">{label}</h3>
            <p className="text-xs text-muted-foreground">{period}</p>
          </div>
        </div>
        <p className="text-center text-muted-foreground py-4">未设置目标</p>
      </div>
    );
  }

  const metrics = [
    { 
      name: '收入', 
      current: progress.current.revenue, 
      target: Number(progress.target.revenue_target),
      progress: progress.progress.revenue,
      format: (v: number) => `¥${(v / 10000).toFixed(1)}万`,
    },
    { 
      name: '线索', 
      current: progress.current.leads, 
      target: progress.target.leads_target,
      progress: progress.progress.leads,
      format: (v: number) => `${v}`,
    },
    { 
      name: '转化', 
      current: progress.current.conversions, 
      target: progress.target.conversions_target,
      progress: progress.progress.conversions,
      format: (v: number) => `${v}`,
    },
    { 
      name: '赢率', 
      current: progress.current.win_rate, 
      target: Number(progress.target.win_rate_target),
      progress: progress.progress.win_rate,
      format: (v: number) => `${v.toFixed(1)}%`,
    },
  ];

  return (
    <div className="bg-card rounded-2xl p-6 border border-border">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center">
          <Target className="w-5 h-5 text-primary-foreground" />
        </div>
        <div>
          <h3 className="font-semibold text-foreground">{label}</h3>
          <p className="text-xs text-muted-foreground">{period}</p>
        </div>
      </div>

      <div className="space-y-4">
        {metrics.map((metric) => (
          <div key={metric.name} className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{metric.name}</span>
              <span className="font-medium text-foreground">
                {metric.format(metric.current)} / {metric.format(metric.target)}
              </span>
            </div>
            <div className="h-2 bg-secondary rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  metric.progress >= 100 ? "bg-success" : metric.progress >= 70 ? "bg-primary" : "bg-warning"
                )}
                style={{ width: `${Math.min(metric.progress, 100)}%` }}
              />
            </div>
            <p className={cn(
              "text-xs text-right",
              metric.progress >= 100 ? "text-success" : metric.progress >= 70 ? "text-primary" : "text-warning"
            )}>
              {metric.progress.toFixed(1)}%
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
