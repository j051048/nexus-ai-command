import { CheckCircle2, CircleAlert, Pencil, Plus } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { SCIENTIFIC_INSTRUMENT_LINES } from '@/config/growthOperatingModel';

import type { SolutionProductOption } from './types';
import { useSaveSolutionProduct } from './useSolutionWorkspace';

interface ProductCatalogManagerProps {
  products: SolutionProductOption[];
}

const EMPTY_PRODUCT: SolutionProductOption & { model_code: string; product_name: string } = {
  instrument_line_code: 'spectroscopy',
  product_name: '',
  model_code: '',
  currency: 'CNY',
  lifecycle_status: 'active',
  validation_status: 'draft',
};

export function ProductCatalogManager({ products }: ProductCatalogManagerProps) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_PRODUCT);
  const saveProduct = useSaveSolutionProduct();
  const verified = products.filter((item) => item.validation_status === 'verified').length;

  const edit = (product?: SolutionProductOption) => {
    setForm(product?.model_code
      ? { ...EMPTY_PRODUCT, ...product, model_code: product.model_code, product_name: product.product_name }
      : EMPTY_PRODUCT);
    setOpen(true);
  };

  const update = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    try {
      await saveProduct.mutateAsync(form);
      toast.success('产品目录已保存，后续配置会自动重新核价');
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '产品目录保存失败');
    }
  };

  return (
    <section className="mb-5 border-y py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium">企业产品目录</h3>
          <p className="text-xs text-muted-foreground">{products.length} 个型号，{verified} 个已审核。只有已审核型号适合正式核价。</p>
        </div>
        <details className="relative">
          <summary className="flex h-9 cursor-pointer list-none items-center rounded-md border px-3 text-sm">查看型号</summary>
          <div className="absolute right-0 z-20 mt-1 max-h-80 w-[min(640px,calc(100vw-3rem))] overflow-auto rounded-md border bg-popover shadow-md">
            <div className="divide-y">
              {products.map((product) => (
                <button key={product.id || product.model_code} type="button" className="grid w-full grid-cols-[minmax(0,1fr)_100px_92px_32px] items-center gap-3 px-3 py-3 text-left text-sm hover:bg-accent" onClick={() => edit(product)}>
                  <span className="min-w-0"><strong className="block truncate">{product.product_name}</strong><span className="text-xs text-muted-foreground">{product.model_code || '未设型号'}</span></span>
                  <span className="text-right tabular-nums">{product.list_price == null ? '待核价' : product.list_price.toLocaleString()}</span>
                  <span className={product.validation_status === 'verified' ? 'text-emerald-700' : 'text-amber-700'}>{product.validation_status === 'verified' ? '已审核' : '待审核'}</span>
                  <Pencil className="h-4 w-4" />
                </button>
              ))}
              {!products.length && <p className="px-4 py-10 text-center text-sm text-muted-foreground">尚未维护产品型号</p>}
            </div>
          </div>
        </details>
        <Button variant="outline" size="sm" onClick={() => edit()}><Plus className="mr-2 h-4 w-4" />新增型号</Button>
      </div>

      {verified < products.length && products.length > 0 && (
        <p className="mt-3 flex items-center gap-2 text-xs text-amber-700"><CircleAlert className="h-3.5 w-3.5" />未审核型号会在配置方案中显示风险提示，不会被静默当作正式报价依据。</p>
      )}
      {products.length > 0 && verified === products.length && (
        <p className="mt-3 flex items-center gap-2 text-xs text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />当前启用型号均已完成目录审核。</p>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>产品型号与商业约束</DialogTitle><DialogDescription>维护可核验的价格、成本、交期和生命周期；复杂兼容规则可通过连接器或后续高级配置扩展。</DialogDescription></DialogHeader>
          <div className="grid gap-4 py-2 md:grid-cols-2">
            <label className="space-y-1.5 text-sm font-medium">产品名称<Input value={form.product_name} onChange={(event) => update('product_name', event.target.value)} /></label>
            <label className="space-y-1.5 text-sm font-medium">型号编码<Input value={form.model_code} onChange={(event) => update('model_code', event.target.value)} /></label>
            <label className="space-y-1.5 text-sm font-medium">仪器谱系<select value={form.instrument_line_code} onChange={(event) => update('instrument_line_code', event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{SCIENTIFIC_INSTRUMENT_LINES.map((line) => <option key={line.code} value={line.code}>{line.name}</option>)}</select></label>
            <label className="space-y-1.5 text-sm font-medium">审核状态<select value={form.validation_status} onChange={(event) => update('validation_status', event.target.value as SolutionProductOption['validation_status'])} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="draft">待审核</option><option value="verified">已审核</option><option value="rejected">已驳回</option></select></label>
            <label className="space-y-1.5 text-sm font-medium">目录价<Input type="number" min={0} value={form.list_price ?? ''} onChange={(event) => update('list_price', event.target.value ? Number(event.target.value) : null)} /></label>
            <label className="space-y-1.5 text-sm font-medium">标准成本<Input type="number" min={0} value={form.standard_cost ?? ''} onChange={(event) => update('standard_cost', event.target.value ? Number(event.target.value) : null)} /></label>
            <label className="space-y-1.5 text-sm font-medium">交期（天）<Input type="number" min={0} value={form.lead_time_days ?? ''} onChange={(event) => update('lead_time_days', event.target.value ? Number(event.target.value) : null)} /></label>
            <label className="space-y-1.5 text-sm font-medium">质保（月）<Input type="number" min={0} value={form.warranty_months ?? ''} onChange={(event) => update('warranty_months', event.target.value ? Number(event.target.value) : null)} /></label>
            <label className="space-y-1.5 text-sm font-medium">生命周期<select value={form.lifecycle_status} onChange={(event) => update('lifecycle_status', event.target.value as SolutionProductOption['lifecycle_status'])} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="active">在售</option><option value="limited">限量/受限</option><option value="eol">停产</option><option value="draft">草稿</option></select></label>
            <label className="space-y-1.5 text-sm font-medium">币种<Input value={form.currency || 'CNY'} onChange={(event) => update('currency', event.target.value.toUpperCase())} /></label>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>取消</Button><Button disabled={saveProduct.isPending || !form.product_name.trim() || !form.model_code.trim()} onClick={submit}>{saveProduct.isPending ? '保存中...' : '保存型号'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
