import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  CARD_TYPE_OPTIONS,
  DATA_SOURCE_OPTIONS,
  type CardType,
} from '@/hooks/useDashboardConfig';
import { BarChart3, PieChart, TrendingUp, Hash, ClipboardList, Trophy } from 'lucide-react';

// ─── 图标映射 ──────────────────────────────────────────────

const TYPE_ICONS: Record<CardType, React.ReactNode> = {
  kpi: <Hash className="w-4 h-4" />,
  bar: <BarChart3 className="w-4 h-4" />,
  pie: <PieChart className="w-4 h-4" />,
  line: <TrendingUp className="w-4 h-4" />,
  approval_stats: <ClipboardList className="w-4 h-4" />,
  leaderboard: <Trophy className="w-4 h-4" />,
};

// ─── Props ──────────────────────────────────────────────────

interface AddCardDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (card: { type: CardType; title: string; dataSource: string }) => void;
}

// ─── 组件 ──────────────────────────────────────────────────

export function AddCardDialog({ open, onOpenChange, onAdd }: AddCardDialogProps) {
  const [type, setType] = useState<CardType>('kpi');
  const [title, setTitle] = useState('');
  const [dataSource, setDataSource] = useState('sales');

  const handleSubmit = () => {
    if (!title.trim()) return;
    onAdd({ type, title: title.trim(), dataSource });
    // 重置
    setType('kpi');
    setTitle('');
    setDataSource('sales');
    onOpenChange(false);
  };

  const handleOpenChange = (val: boolean) => {
    if (!val) {
      setType('kpi');
      setTitle('');
      setDataSource('sales');
    }
    onOpenChange(val);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>添加仪表板卡片</DialogTitle>
          <DialogDescription>选择卡片类型、标题和数据源以添加新卡片到仪表板。</DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-4">
          {/* 卡片类型 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">卡片类型</Label>
            <RadioGroup
              value={type}
              onValueChange={(val) => setType(val as CardType)}
              className="grid grid-cols-1 sm:grid-cols-2 gap-2"
            >
              {CARD_TYPE_OPTIONS.map((opt) => (
                <Label
                  key={opt.value}
                  htmlFor={`type-${opt.value}`}
                  className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-all hover:bg-muted/50 ${
                    type === opt.value ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border'
                  }`}
                >
                  <RadioGroupItem value={opt.value} id={`type-${opt.value}`} className="sr-only" />
                  <span className="text-primary">{TYPE_ICONS[opt.value]}</span>
                  <span className="text-sm">{opt.label}</span>
                </Label>
              ))}
            </RadioGroup>
          </div>

          {/* 标题 */}
          <div className="space-y-2">
            <Label htmlFor="card-title" className="text-sm font-medium">
              卡片标题
            </Label>
            <Input
              id="card-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="请输入卡片标题"
              className="bg-background/50"
            />
          </div>

          {/* 数据源 */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">数据源</Label>
            <Select value={dataSource} onValueChange={setDataSource}>
              <SelectTrigger className="bg-background/50">
                <SelectValue placeholder="选择数据源" />
              </SelectTrigger>
              <SelectContent>
                {DATA_SOURCE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 预览提示 */}
          <div className="p-3 rounded-lg bg-muted/50 border border-dashed border-border">
            <p className="text-xs text-muted-foreground">
              预览：
              <span className="font-medium text-foreground ml-1">{title || '(未命名)'}</span>
              <span className="mx-1">/</span>
              <span className="font-medium text-foreground">
                {CARD_TYPE_OPTIONS.find((o) => o.value === type)?.label}
              </span>
              <span className="mx-1">/</span>
              <span className="font-medium text-foreground">
                {DATA_SOURCE_OPTIONS.find((o) => o.value === dataSource)?.label}
              </span>
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={!title.trim()}>
            添加
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default AddCardDialog;
