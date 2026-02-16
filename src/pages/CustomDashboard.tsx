import React, { useState, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  LayoutGrid,
  Plus,
  Pencil,
  Check,
  RotateCcw,
  GripVertical,
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { useDashboardConfig, CARD_TYPE_OPTIONS } from '@/hooks/useDashboardConfig';
import type { CardType } from '@/hooks/useDashboardConfig';
import { DashboardCard } from '@/components/dashboard/DashboardCard';
import { AddCardDialog } from '@/components/dashboard/AddCardDialog';

// ─── 页面组件 ──────────────────────────────────────────────

function CustomDashboard() {
  const { config, addCard, removeCard, updateCard, resetConfig } = useDashboardConfig();
  const [isEditing, setIsEditing] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [editingCardId, setEditingCardId] = useState<string | null>(null);

  // ─── 操作回调 ──────────────────────────────────────────

  const handleAddCard = useCallback(
    (card: { type: string; title: string; dataSource: string }) => {
      addCard({
        type: card.type as CardType,
        title: card.title,
        dataSource: card.dataSource,
      });
      toast.success(`已添加卡片「${card.title}」`);
    },
    [addCard],
  );

  const handleRemoveCard = useCallback(
    (cardId: string) => {
      const card = config.cards.find((c) => c.id === cardId);
      removeCard(cardId);
      toast.success(`已移除卡片「${card?.title || ''}」`);
    },
    [config.cards, removeCard],
  );

  const handleEditCard = useCallback((cardId: string) => {
    setEditingCardId(cardId);
  }, []);

  const handleReset = useCallback(() => {
    resetConfig();
    setShowResetDialog(false);
    toast.success('已恢复默认布局');
  }, [resetConfig]);

  const toggleEditing = useCallback(() => {
    setIsEditing((prev) => {
      if (prev) {
        toast.success('布局已自动保存');
      }
      return !prev;
    });
  }, []);

  // ─── 编辑中的卡片配置 ──────────────────────────────────

  const editingCard = editingCardId ? config.cards.find((c) => c.id === editingCardId) : null;

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      {/* 页面标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <LayoutGrid className="w-7 h-7 text-primary" />
            自定义仪表板
          </h1>
          <p className="text-sm text-muted-foreground">
            自由配置仪表板卡片，打造专属数据视图
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isEditing && (
            <>
              <Button variant="outline" size="sm" onClick={() => setShowAddDialog(true)}>
                <Plus className="w-4 h-4 mr-1" />
                添加卡片
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowResetDialog(true)}>
                <RotateCcw className="w-4 h-4 mr-1" />
                重置
              </Button>
            </>
          )}
          <Button
            variant={isEditing ? 'default' : 'outline'}
            size="sm"
            onClick={toggleEditing}
          >
            {isEditing ? (
              <>
                <Check className="w-4 h-4 mr-1" />
                完成编辑
              </>
            ) : (
              <>
                <Pencil className="w-4 h-4 mr-1" />
                编辑布局
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 编辑模式横幅 */}
      {isEditing && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-primary/5 border border-primary/20 text-sm">
          <GripVertical className="w-4 h-4 text-primary shrink-0" />
          <span className="text-muted-foreground">
            编辑模式已开启 —— 点击
            <Badge variant="secondary" className="mx-1 text-xs">
              +
            </Badge>
            添加卡片，点击
            <Badge variant="secondary" className="mx-1 text-xs">
              x
            </Badge>
            删除卡片。布局将自动保存到本地。
          </span>
        </div>
      )}

      {/* 卡片网格 */}
      {config.cards.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <LayoutGrid className="w-12 h-12 text-muted-foreground/50 mb-4" />
            <p className="text-muted-foreground mb-2">仪表板为空</p>
            <p className="text-sm text-muted-foreground mb-4">点击下方按钮添加您的第一个卡片</p>
            <Button variant="outline" onClick={() => { setIsEditing(true); setShowAddDialog(true); }}>
              <Plus className="w-4 h-4 mr-1" />
              添加卡片
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {config.cards.map((card) => (
            <DashboardCard
              key={card.id}
              config={card}
              isEditing={isEditing}
              onRemove={handleRemoveCard}
              onEdit={handleEditCard}
            />
          ))}

          {/* 编辑模式下的添加按钮 */}
          {isEditing && (
            <Card
              className="border-dashed border-2 cursor-pointer hover:bg-muted/30 transition-colors flex items-center justify-center min-h-[160px]"
              onClick={() => setShowAddDialog(true)}
            >
              <CardContent className="flex flex-col items-center gap-2 p-6">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <Plus className="w-5 h-5 text-primary" />
                </div>
                <span className="text-sm text-muted-foreground">添加卡片</span>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* 底部统计 */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground pt-4 border-t">
        <span>
          共 <Badge variant="secondary" className="text-xs mx-1">{config.cards.length}</Badge> 张卡片
        </span>
        <span>
          类型分布：
          {CARD_TYPE_OPTIONS.map((opt) => {
            const count = config.cards.filter((c) => c.type === opt.value).length;
            return count > 0 ? (
              <Badge key={opt.value} variant="outline" className="text-xs mx-0.5">
                {opt.label} {count}
              </Badge>
            ) : null;
          })}
        </span>
      </div>

      {/* 添加卡片弹窗 */}
      <AddCardDialog
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
        onAdd={handleAddCard}
      />

      {/* 重置确认弹窗 */}
      <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认重置布局？</AlertDialogTitle>
            <AlertDialogDescription>
              这将恢复仪表板到默认布局，您当前的自定义配置将丢失。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleReset}>确认重置</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 编辑卡片弹窗（简单实现） */}
      {editingCard && (
        <EditCardDialog
          card={editingCard}
          open={!!editingCardId}
          onOpenChange={(open) => { if (!open) setEditingCardId(null); }}
          onSave={(id, updates) => {
            updateCard(id, updates);
            setEditingCardId(null);
            toast.success('卡片已更新');
          }}
        />
      )}
    </div>
  );
}

// ─── 编辑卡片弹窗 ──────────────────────────────────────────

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DATA_SOURCE_OPTIONS, type DashboardCardConfig } from '@/hooks/useDashboardConfig';

interface EditCardDialogProps {
  card: DashboardCardConfig;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (id: string, updates: Partial<DashboardCardConfig>) => void;
}

function EditCardDialog({ card, open, onOpenChange, onSave }: EditCardDialogProps) {
  const [title, setTitle] = useState(card.title);
  const [dataSource, setDataSource] = useState(card.dataSource);

  React.useEffect(() => {
    setTitle(card.title);
    setDataSource(card.dataSource);
  }, [card]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>编辑卡片</DialogTitle>
          <DialogDescription>修改卡片标题和数据源。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>标题</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>数据源</Label>
            <Select value={dataSource} onValueChange={setDataSource}>
              <SelectTrigger>
                <SelectValue />
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
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            onClick={() => onSave(card.id, { title: title.trim(), dataSource })}
            disabled={!title.trim()}
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default CustomDashboard;
