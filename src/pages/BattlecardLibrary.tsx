/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * 竞品打击库页面
 * 动态数据驱动 + admin/boss 可管理竞品、产品、对比维度
 */

import React, { useState, useMemo } from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend } from 'recharts';
import { useAuth } from '@/components/auth/AuthContext';
import { useDebounce } from '@/hooks/useDebounce';
import {
  useCompetitors,
  useCompetitorDetail,
  useCreateCompetitor,
  useUpdateCompetitor,
  useDeleteCompetitor,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
  useUpsertFeature,
  useDeleteFeature,
} from '@/hooks/useCompetitors';
import type {
  Competitor,
  CompetitorProduct,
  CompetitorFeature,
  CompetitorDetail,
} from '@/hooks/useCompetitors';
import { NoDataYet, NoSearchResults } from '@/components/common/EmptyState';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import {
  Search,
  Plus,
  Swords,
  ShieldAlert,
  TrendingUp,
  Pencil,
  Trash2,
  Loader2,
  MoreHorizontal,
  Package,
  BarChart3,
  Star,
  Globe,
  Building2,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';

// ─── 威胁等级配置 ──────────────────────────────────
const THREAT_LEVELS: Record<string, { label: string; color: string; icon: string }> = {
  low: { label: '低', color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400', icon: '🟢' },
  medium: { label: '中', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400', icon: '🟡' },
  high: { label: '高', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400', icon: '🟠' },
  critical: { label: '极高', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400', icon: '🔴' },
};

// ─── 竞品编辑弹窗 ──────────────────────────────────
function CompetitorFormDialog({
  open,
  onOpenChange,
  competitor,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  competitor?: Competitor | null;
}) {
  const isEdit = !!competitor;
  const createMut = useCreateCompetitor();
  const updateMut = useUpdateCompetitor();

  const [form, setForm] = useState({
    name: '',
    brand_names: '',
    industry: '',
    tag: '',
    website: '',
    description: '',
    strength_summary: '',
    weakness_summary: '',
    threat_level: 'medium',
    sort_order: 0,
  });

  React.useEffect(() => {
    if (open && competitor) {
      setForm({
        name: competitor.name || '',
        brand_names: (competitor.brand_names || []).join(', '),
        industry: competitor.industry || '',
        tag: competitor.tag || '',
        website: competitor.website || '',
        description: competitor.description || '',
        strength_summary: competitor.strength_summary || '',
        weakness_summary: competitor.weakness_summary || '',
        threat_level: competitor.threat_level || 'medium',
        sort_order: competitor.sort_order || 0,
      });
    } else if (open) {
      setForm({
        name: '', brand_names: '', industry: '', tag: '', website: '',
        description: '', strength_summary: '', weakness_summary: '',
        threat_level: 'medium', sort_order: 0,
      });
    }
  }, [open, competitor]);

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入竞品名称');
      return;
    }
    const payload: any = {
      ...form,
      brand_names: form.brand_names ? form.brand_names.split(/[,，]/).map(s => s.trim()).filter(Boolean) : [],
      sort_order: Number(form.sort_order) || 0,
    };
    try {
      if (isEdit && competitor) {
        await updateMut.mutateAsync({ id: competitor.id, data: payload });
      } else {
        await createMut.mutateAsync(payload);
      }
      onOpenChange(false);
    } catch {
      // error handled by hook
    }
  };

  const loading = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑竞品' : '添加竞品'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '修改竞品公司的基本信息' : '录入新的竞争对手信息'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>公司名称 *</Label>
              <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="如：安捷伦科技" />
            </div>
            <div className="space-y-2">
              <Label>标签</Label>
              <Input value={form.tag} onChange={e => setForm(p => ({ ...p, tag: e.target.value }))} placeholder="如：进口巨头" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>行业</Label>
              <Input value={form.industry} onChange={e => setForm(p => ({ ...p, industry: e.target.value }))} placeholder="如：科学仪器" />
            </div>
            <div className="space-y-2">
              <Label>威胁等级</Label>
              <Select value={form.threat_level} onValueChange={v => setForm(p => ({ ...p, threat_level: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(THREAT_LEVELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v.icon} {v.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>品牌名 / 别名（逗号分隔）</Label>
            <Input value={form.brand_names} onChange={e => setForm(p => ({ ...p, brand_names: e.target.value }))} placeholder="如：Agilent, 安捷伦" />
          </div>

          <div className="space-y-2">
            <Label>官网</Label>
            <Input value={form.website} onChange={e => setForm(p => ({ ...p, website: e.target.value }))} placeholder="https://..." />
          </div>

          <div className="space-y-2">
            <Label>简介</Label>
            <Textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} rows={2} placeholder="竞品公司的简要介绍" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>对手优势</Label>
              <Textarea value={form.strength_summary} onChange={e => setForm(p => ({ ...p, strength_summary: e.target.value }))} rows={3} placeholder="对手的核心优势..." />
            </div>
            <div className="space-y-2">
              <Label>对手劣势</Label>
              <Textarea value={form.weakness_summary} onChange={e => setForm(p => ({ ...p, weakness_summary: e.target.value }))} rows={3} placeholder="对手的核心劣势..." />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {isEdit ? '保存' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── 产品编辑弹窗 ──────────────────────────────────
function ProductFormDialog({
  open,
  onOpenChange,
  competitorId,
  product,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  competitorId: string;
  product?: CompetitorProduct | null;
}) {
  const isEdit = !!product;
  const createMut = useCreateProduct();
  const updateMut = useUpdateProduct();

  const [form, setForm] = useState({
    name: '', model: '', category: '', price_range: '',
    description: '', our_competing_product: '', comparison_notes: '',
  });

  React.useEffect(() => {
    if (open && product) {
      setForm({
        name: product.name || '',
        model: product.model || '',
        category: product.category || '',
        price_range: product.price_range || '',
        description: product.description || '',
        our_competing_product: product.our_competing_product || '',
        comparison_notes: product.comparison_notes || '',
      });
    } else if (open) {
      setForm({ name: '', model: '', category: '', price_range: '', description: '', our_competing_product: '', comparison_notes: '' });
    }
  }, [open, product]);

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      toast.error('请输入产品名称');
      return;
    }
    try {
      if (isEdit && product) {
        await updateMut.mutateAsync({ competitorId, productId: product.id, data: form });
      } else {
        await createMut.mutateAsync({ competitorId, data: form });
      }
      onOpenChange(false);
    } catch {
      // error handled by hook
    }
  };

  const loading = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑产品' : '添加竞品产品'}</DialogTitle>
          <DialogDescription>录入竞争对手的产品信息，以便对比分析</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>产品名称 *</Label>
              <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="产品名" />
            </div>
            <div className="space-y-2">
              <Label>型号</Label>
              <Input value={form.model} onChange={e => setForm(p => ({ ...p, model: e.target.value }))} placeholder="如：7890B" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>分类</Label>
              <Input value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))} placeholder="如：气相色谱" />
            </div>
            <div className="space-y-2">
              <Label>价格区间</Label>
              <Input value={form.price_range} onChange={e => setForm(p => ({ ...p, price_range: e.target.value }))} placeholder="如：50-80万" />
            </div>
          </div>
          <div className="space-y-2">
            <Label>产品描述</Label>
            <Textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} rows={2} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>我方对标产品</Label>
              <Input value={form.our_competing_product} onChange={e => setForm(p => ({ ...p, our_competing_product: e.target.value }))} placeholder="我们的对标产品名" />
            </div>
          </div>
          <div className="space-y-2">
            <Label>对比备注</Label>
            <Textarea value={form.comparison_notes} onChange={e => setForm(p => ({ ...p, comparison_notes: e.target.value }))} rows={2} placeholder="与我方产品的对比要点..." />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {isEdit ? '保存' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── 对比维度编辑弹窗 ──────────────────────────────
function FeatureFormDialog({
  open,
  onOpenChange,
  competitorId,
  feature,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  competitorId: string;
  feature?: CompetitorFeature | null;
}) {
  const upsertMut = useUpsertFeature();

  const [form, setForm] = useState({
    id: undefined as string | undefined,
    dimension: '', competitor_score: '', our_score: '',
    competitor_detail: '', our_advantage: '', counter_strategy: '',
  });

  React.useEffect(() => {
    if (open && feature) {
      setForm({
        id: feature.id,
        dimension: feature.dimension || '',
        competitor_score: feature.competitor_score?.toString() || '',
        our_score: feature.our_score?.toString() || '',
        competitor_detail: feature.competitor_detail || '',
        our_advantage: feature.our_advantage || '',
        counter_strategy: feature.counter_strategy || '',
      });
    } else if (open) {
      setForm({ id: undefined, dimension: '', competitor_score: '', our_score: '', competitor_detail: '', our_advantage: '', counter_strategy: '' });
    }
  }, [open, feature]);

  const handleSubmit = async () => {
    if (!form.dimension.trim()) {
      toast.error('请输入对比维度名称');
      return;
    }
    const payload: any = {
      ...form,
      competitor_score: form.competitor_score ? Number(form.competitor_score) : null,
      our_score: form.our_score ? Number(form.our_score) : null,
    };
    try {
      await upsertMut.mutateAsync({ competitorId, data: payload });
      onOpenChange(false);
    } catch {
      // error handled by hook
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{feature ? '编辑对比维度' : '添加对比维度'}</DialogTitle>
          <DialogDescription>维度化对比双方能力，制定打击策略</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>维度名称 *</Label>
            <Input value={form.dimension} onChange={e => setForm(p => ({ ...p, dimension: e.target.value }))} placeholder="如：技术支持响应速度" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>对手评分 (1-10)</Label>
              <Input type="number" min={1} max={10} value={form.competitor_score} onChange={e => setForm(p => ({ ...p, competitor_score: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>我方评分 (1-10)</Label>
              <Input type="number" min={1} max={10} value={form.our_score} onChange={e => setForm(p => ({ ...p, our_score: e.target.value }))} />
            </div>
          </div>
          <div className="space-y-2">
            <Label>对手详情</Label>
            <Textarea value={form.competitor_detail} onChange={e => setForm(p => ({ ...p, competitor_detail: e.target.value }))} rows={2} placeholder="对手在此维度的具体表现..." />
          </div>
          <div className="space-y-2">
            <Label>我方优势</Label>
            <Textarea value={form.our_advantage} onChange={e => setForm(p => ({ ...p, our_advantage: e.target.value }))} rows={2} placeholder="我们在此维度的竞争优势..." />
          </div>
          <div className="space-y-2">
            <Label>应对策略</Label>
            <Textarea value={form.counter_strategy} onChange={e => setForm(p => ({ ...p, counter_strategy: e.target.value }))} rows={2} placeholder="面对客户提到该维度时的应对话术..." />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={upsertMut.isPending}>
            {upsertMut.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── 评分条 ────────────────────────────────────────
function ScoreBar({ score, max = 10, color }: { score: number | null; max?: number; color: string }) {
  if (!score) return <span className="text-muted-foreground text-xs">-</span>;
  const pct = (score / max) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium w-5 text-right">{score}</span>
    </div>
  );
}

// ─── 竞品详情面板 ──────────────────────────────────
function CompetitorDetailPanel({
  detail,
  isLoading,
  canEdit,
  onEditCompetitor,
  onDeleteCompetitor,
}: {
  detail: CompetitorDetail | undefined;
  isLoading: boolean;
  canEdit: boolean;
  onEditCompetitor: () => void;
  onDeleteCompetitor: () => void;
}) {
  const [productDialog, setProductDialog] = useState<{ open: boolean; product: CompetitorProduct | null }>({ open: false, product: null });
  const [featureDialog, setFeatureDialog] = useState<{ open: boolean; feature: CompetitorFeature | null }>({ open: false, feature: null });
  const deleteProductMut = useDeleteProduct();
  const deleteFeatureMut = useDeleteFeature();
  const { confirm, ConfirmDialogProps } = useConfirmDialog();

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex flex-col items-center justify-center h-[500px] border-2 border-dashed rounded-2xl opacity-30">
        <Swords className="w-16 h-16 mb-4" />
        <p className="text-xl font-medium">选择左侧竞品查看详情</p>
      </div>
    );
  }

  const { competitor: comp, products = [], features = [] } = detail;
  const threat = THREAT_LEVELS[comp.threat_level] || THREAT_LEVELS.medium;

  const handleDeleteProduct = async (p: CompetitorProduct) => {
    const ok = await confirm({ title: '删除产品', description: `确认删除产品「${p.name}」？`, variant: 'destructive' });
    if (ok) deleteProductMut.mutate({ competitorId: comp.id, productId: p.id });
  };

  const handleDeleteFeature = async (f: CompetitorFeature) => {
    const ok = await confirm({ title: '删除维度', description: `确认删除对比维度「${f.dimension}」？`, variant: 'destructive' });
    if (ok) deleteFeatureMut.mutate({ competitorId: comp.id, featureId: f.id });
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
      <ConfirmDialog {...ConfirmDialogProps} />
      <ProductFormDialog
        open={productDialog.open}
        onOpenChange={v => setProductDialog(p => ({ ...p, open: v }))}
        competitorId={comp.id}
        product={productDialog.product}
      />
      <FeatureFormDialog
        open={featureDialog.open}
        onOpenChange={v => setFeatureDialog(p => ({ ...p, open: v }))}
        competitorId={comp.id}
        feature={featureDialog.feature}
      />

      {/* Header */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                <Swords className="w-7 h-7 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-2xl font-bold">{comp.name}</h2>
                  {comp.tag && <Badge variant="secondary">{comp.tag}</Badge>}
                  <Badge className={cn('text-xs', threat.color)}>{threat.icon} {threat.label}</Badge>
                </div>
                <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                  {comp.industry && <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" />{comp.industry}</span>}
                  {comp.website && <a href={comp.website} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-primary"><Globe className="w-3.5 h-3.5" />{comp.website}</a>}
                  {comp.brand_names?.length > 0 && <span>别名: {comp.brand_names.join(', ')}</span>}
                </div>
              </div>
            </div>
            {canEdit && (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onEditCompetitor}>
                  <Pencil className="w-3.5 h-3.5 mr-1" /> 编辑
                </Button>
                <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={onDeleteCompetitor}>
                  <Trash2 className="w-3.5 h-3.5 mr-1" /> 删除
                </Button>
              </div>
            )}
          </div>
          {comp.description && <p className="mt-3 text-sm text-muted-foreground">{comp.description}</p>}
        </CardContent>
      </Card>

      {/* 优劣势 */}
      {(comp.strength_summary || comp.weakness_summary) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {comp.strength_summary && (
            <Card className="border-l-4 border-l-orange-400">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-orange-500" /> 对手优势
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{comp.strength_summary}</p>
              </CardContent>
            </Card>
          )}
          {comp.weakness_summary && (
            <Card className="border-l-4 border-l-green-500">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-green-600" /> 对手劣势（打击点）
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{comp.weakness_summary}</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Tabs: 产品 / 对比维度 */}
      <Tabs defaultValue="products">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="products" className="gap-1.5">
              <Package className="w-4 h-4" /> 竞品产品 ({products.length})
            </TabsTrigger>
            <TabsTrigger value="features" className="gap-1.5">
              <BarChart3 className="w-4 h-4" /> 对比维度 ({features.length})
            </TabsTrigger>
          </TabsList>
          {canEdit && (
            <Tabs defaultValue="products">
              {/* Use hidden trick to get current tab for add button */}
            </Tabs>
          )}
        </div>

        {/* 产品 Tab */}
        <TabsContent value="products" className="mt-4">
          {canEdit && (
            <div className="mb-4">
              <Button size="sm" variant="outline" onClick={() => setProductDialog({ open: true, product: null })}>
                <Plus className="w-4 h-4 mr-1" /> 添加产品
              </Button>
            </div>
          )}
          {products.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              暂无竞品产品数据
              {canEdit && '，点击上方按钮添加'}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {products.map(p => (
                <Card key={p.id} className="group">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold truncate">{p.name}</span>
                          {p.model && <Badge variant="outline" className="text-[10px] shrink-0">{p.model}</Badge>}
                        </div>
                        {p.category && <p className="text-xs text-muted-foreground mt-0.5">{p.category}</p>}
                      </div>
                      {canEdit && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setProductDialog({ open: true, product: p })}>
                              <Pencil className="w-3.5 h-3.5 mr-2" /> 编辑
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-destructive" onClick={() => handleDeleteProduct(p)}>
                              <Trash2 className="w-3.5 h-3.5 mr-2" /> 删除
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                    {p.price_range && (
                      <p className="text-sm mt-2"><span className="text-muted-foreground">价格:</span> {p.price_range}</p>
                    )}
                    {p.our_competing_product && (
                      <p className="text-sm"><span className="text-muted-foreground">我方对标:</span> <span className="text-primary font-medium">{p.our_competing_product}</span></p>
                    )}
                    {p.description && <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{p.description}</p>}
                    {p.comparison_notes && (
                      <p className="text-xs mt-1 text-muted-foreground italic border-l-2 border-primary/30 pl-2">{p.comparison_notes}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* 对比维度 Tab */}
        <TabsContent value="features" className="mt-4">
          {canEdit && (
            <div className="mb-4">
              <Button size="sm" variant="outline" onClick={() => setFeatureDialog({ open: true, feature: null })}>
                <Plus className="w-4 h-4 mr-1" /> 添加维度
              </Button>
            </div>
          )}
          {features.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              暂无对比维度数据
              {canEdit && '，点击上方按钮添加'}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Radar Chart Overview */}
              {features.filter(f => f.competitor_score && f.our_score).length >= 3 && (
                <Card>
                  <CardContent className="p-4">
                    <ResponsiveContainer width="100%" height={280}>
                      <RadarChart data={features.filter(f => f.competitor_score && f.our_score).map(f => ({
                        dimension: f.dimension.length > 6 ? f.dimension.slice(0, 6) + '…' : f.dimension,
                        competitor: f.competitor_score,
                        ours: f.our_score,
                      }))}>
                        <PolarGrid strokeDasharray="3 3" />
                        <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
                        <PolarRadiusAxis angle={90} domain={[0, 10]} tick={{ fontSize: 10 }} />
                        <Radar name="对手" dataKey="competitor" stroke="#f97316" fill="#f97316" fillOpacity={0.2} />
                        <Radar name="我方" dataKey="ours" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.2} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              )}

              {/* Detail Cards */}
              {features.map(f => (
                <Card key={f.id} className="group">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="font-semibold text-sm">{f.dimension}</h4>
                      {canEdit && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setFeatureDialog({ open: true, feature: f })}>
                              <Pencil className="w-3.5 h-3.5 mr-2" /> 编辑
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-destructive" onClick={() => handleDeleteFeature(f)}>
                              <Trash2 className="w-3.5 h-3.5 mr-2" /> 删除
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-4 mb-2">
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase mb-1">对手</p>
                        <ScoreBar score={f.competitor_score} color="bg-orange-500" />
                      </div>
                      <div>
                        <p className="text-[10px] text-muted-foreground uppercase mb-1">我方</p>
                        <ScoreBar score={f.our_score} color="bg-primary" />
                      </div>
                    </div>
                    {f.counter_strategy && (
                      <div className="mt-2 p-2 rounded-lg bg-primary/5 border border-primary/10">
                        <p className="text-xs"><span className="font-medium text-primary">应对策略:</span> {f.counter_strategy}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── 主页面 ────────────────────────────────────────
export function BattlecardLibrary() {
  const { role } = useAuth();
  // 放开权限，允许业务人员（销售、员工）维护竞品库
  const canEdit = ['boss', 'manager', 'sales', 'employee'].includes(role || 'boss');

  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebounce(searchTerm, 300);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // 弹窗状态
  const [competitorDialog, setCompetitorDialog] = useState<{ open: boolean; competitor: Competitor | null }>({ open: false, competitor: null });
  const { confirm, ConfirmDialogProps } = useConfirmDialog();

  // 数据
  const { data: competitors = [], isLoading: listLoading } = useCompetitors();
  const { data: detail, isLoading: detailLoading } = useCompetitorDetail(selectedId);
  const deleteMut = useDeleteCompetitor();

  // 搜索过滤
  const filtered = useMemo(() => {
    if (!debouncedSearch) return competitors;
    const q = debouncedSearch.toLowerCase();
    return competitors.filter(
      c =>
        c.name.toLowerCase().includes(q) ||
        c.tag?.toLowerCase().includes(q) ||
        c.industry?.toLowerCase().includes(q) ||
        c.brand_names?.some(b => b.toLowerCase().includes(q))
    );
  }, [competitors, debouncedSearch]);

  // 自动选中第一个
  React.useEffect(() => {
    if (!selectedId && filtered.length > 0) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  const handleDeleteCompetitor = async () => {
    if (!detail?.competitor) return;
    const ok = await confirm({
      title: '删除竞品',
      description: `确认删除竞品「${detail.competitor.name}」？关联的产品和对比维度也将被删除。此操作不可撤销。`,
      variant: 'destructive',
    });
    if (ok) {
      deleteMut.mutate(detail.competitor.id, {
        onSuccess: () => setSelectedId(null),
      });
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto pb-20">
      <ConfirmDialog {...ConfirmDialogProps} />
      <CompetitorFormDialog
        open={competitorDialog.open}
        onOpenChange={v => setCompetitorDialog(p => ({ ...p, open: v }))}
        competitor={competitorDialog.competitor}
      />

      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <Swords className="w-7 h-7 text-primary" />
            竞品打击库
          </h1>
          <p className="text-muted-foreground mt-1">知己知彼，维护竞品情报与打击策略</p>
        </div>
        {canEdit && (
          <Button onClick={() => setCompetitorDialog({ open: true, competitor: null })}>
            <Plus className="w-4 h-4 mr-2" /> 添加竞品
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* 左侧列表 */}
        <div className="lg:col-span-4 xl:col-span-3 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="搜索竞品..."
              className="pl-10"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>

          <ScrollArea className="h-[calc(100vh-280px)]">
            <div className="space-y-2 pr-2">
              {listLoading ? (
                Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)
              ) : filtered.length === 0 ? (
                competitors.length === 0 ? (
                  <NoDataYet resourceName="竞品" onAdd={canEdit ? () => setCompetitorDialog({ open: true, competitor: null }) : undefined} />
                ) : (
                  <NoSearchResults query={debouncedSearch} onClear={() => setSearchTerm('')} />
                )
              ) : (
                filtered.map(c => {
                  const threat = THREAT_LEVELS[c.threat_level] || THREAT_LEVELS.medium;
                  const isSelected = selectedId === c.id;
                  return (
                    <Card
                      key={c.id}
                      className={cn(
                        'cursor-pointer transition-all hover:border-primary/40',
                        isSelected && 'border-primary bg-primary/5 shadow-sm'
                      )}
                      onClick={() => setSelectedId(c.id)}
                    >
                      <CardContent className="p-3.5">
                        <div className="flex items-center justify-between">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold truncate">{c.name}</span>
                              {c.tag && <Badge variant="secondary" className="text-[10px] shrink-0">{c.tag}</Badge>}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className={cn('text-[10px] border-none', threat.color)}>
                                {threat.icon} {threat.label}
                              </Badge>
                              {c.industry && <span className="text-xs text-muted-foreground">{c.industry}</span>}
                            </div>
                          </div>
                          <ChevronRight className={cn(
                            'w-4 h-4 text-muted-foreground transition-colors shrink-0',
                            isSelected && 'text-primary'
                          )} />
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </div>

        {/* 右侧详情 */}
        <div className="lg:col-span-8 xl:col-span-9">
          <CompetitorDetailPanel
            detail={detail}
            isLoading={detailLoading && !!selectedId}
            canEdit={canEdit}
            onEditCompetitor={() => {
              if (detail?.competitor) setCompetitorDialog({ open: true, competitor: detail.competitor });
            }}
            onDeleteCompetitor={handleDeleteCompetitor}
          />
        </div>
      </div>
    </div>
  );
}
