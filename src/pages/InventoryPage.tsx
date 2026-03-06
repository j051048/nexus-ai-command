import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import {
  Warehouse,
  Plus,
  Loader2,
  Search,
  ArrowDownToLine,
  ArrowUpFromLine,
  AlertTriangle,
  PackageCheck,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface InventoryItem {
  id: string;
  item_code: string;
  name: string;
  category: string;
  quantity: number;
  min_stock: number;
  location?: string;
  unit?: string;
  created_at: string;
}

export default function InventoryPage() {
  const { profile } = useAuth();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [ioDialogOpen, setIoDialogOpen] = useState(false);
  const [ioType, setIoType] = useState<'in' | 'out'>('in');
  const [selectedItem, setSelectedItem] = useState<InventoryItem | null>(null);
  const [ioQuantity, setIoQuantity] = useState('');
  const [ioReason, setIoReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    item_code: '',
    name: '',
    category: 'office',
    quantity: '',
    min_stock: '10',
    location: '',
    unit: '个',
  });

  const orgId = profile?.organization_id;

  const fetchItems = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      let query = supabase
        .from('inventory')
        .select('*')
        .eq('organization_id', orgId)
        .order('name', { ascending: true });

      if (filterCategory !== 'all') query = query.eq('category', filterCategory);
      if (search.trim()) query = query.ilike('name', `%${search.trim()}%`);

      const { data, error } = await query;
      if (error) throw error;
      let result = (data as InventoryItem[]) || [];
      if (lowStockOnly) result = result.filter((i) => i.quantity <= i.min_stock);
      setItems(result);
    } catch (e) {
      toast.error('加载库存失败: ' + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [orgId, filterCategory, search, lowStockOnly]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleCreate = async () => {
    if (!form.item_code.trim() || !form.name.trim()) {
      toast.error('物料编码和名称不能为空');
      return;
    }
    setSubmitting(true);
    try {
      // @ts-expect-error Types not fully generated
      const { error } = await supabase.from('inventory').insert({
        item_code: form.item_code.trim(),
        name: form.name.trim(),
        category: form.category,
        quantity: Number(form.quantity) || 0,
        min_stock: Number(form.min_stock) || 10,
        location: form.location.trim() || null,
        unit: form.unit || '个',
        organization_id: orgId,
      });
      if (error) throw error;
      toast.success('物料添加成功');
      setDialogOpen(false);
      setForm({ item_code: '', name: '', category: 'office', quantity: '', min_stock: '10', location: '', unit: '个' });
      fetchItems();
    } catch (e) {
      toast.error('创建失败: ' + (e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleIO = async () => {
    if (!selectedItem || !ioQuantity || Number(ioQuantity) <= 0) {
      toast.error('请输入有效数量');
      return;
    }
    const qty = Number(ioQuantity);
    if (ioType === 'out' && qty > selectedItem.quantity) {
      toast.error('出库数量不能超过库存');
      return;
    }
    setSubmitting(true);
    try {
      const newQty = ioType === 'in' ? selectedItem.quantity + qty : selectedItem.quantity - qty;
      const { error } = await supabase
        .from('inventory')
        // @ts-expect-error Types not fully generated
        .update({ quantity: newQty })
        .eq('id', selectedItem.id);
      if (error) throw error;
      toast.success(`${ioType === 'in' ? '入库' : '出库'}成功，当前库存: ${newQty}`);
      setIoDialogOpen(false);
      setIoQuantity('');
      setIoReason('');
      fetchItems();
    } catch (e) {
      toast.error('操作失败: ' + (e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const openIO = (item: InventoryItem, type: 'in' | 'out') => {
    setSelectedItem(item);
    setIoType(type);
    setIoDialogOpen(true);
  };

  const stats = {
    total: items.length,
    lowStock: items.filter((i) => i.quantity <= i.min_stock).length,
    totalQty: items.reduce((sum, i) => sum + i.quantity, 0),
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Warehouse className="h-6 w-6" /> 库存管理
          </h1>
          <p className="text-sm text-muted-foreground mt-1">管理出入库、盘点和库存预警</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" /> 新增物料
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          { label: '物料种类', value: stats.total },
          { label: '库存总量', value: stats.totalQty.toLocaleString() },
          { label: '低库存预警', value: stats.lowStock, color: stats.lowStock > 0 ? 'text-amber-500' : '' },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-4 pb-3 px-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className={cn('text-2xl font-bold', (s as { color?: string }).color)}>{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="搜索物料..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={filterCategory} onValueChange={setFilterCategory}>
          <SelectTrigger className="w-[130px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部分类</SelectItem>
            <SelectItem value="office">办公用品</SelectItem>
            <SelectItem value="hardware">硬件设备</SelectItem>
            <SelectItem value="material">原材料</SelectItem>
            <SelectItem value="consumable">耗材</SelectItem>
            <SelectItem value="other">其他</SelectItem>
          </SelectContent>
        </Select>
        <Button
          variant={lowStockOnly ? 'default' : 'outline'}
          size="sm"
          className="gap-1.5"
          onClick={() => setLowStockOnly(!lowStockOnly)}
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          低库存
        </Button>
      </div>

      {/* Inventory Table */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-16">
          <Warehouse className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
          <p className="text-muted-foreground">暂无库存记录</p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium">物料编码</th>
                <th className="text-left px-4 py-3 font-medium">名称</th>
                <th className="text-left px-4 py-3 font-medium">分类</th>
                <th className="text-right px-4 py-3 font-medium">库存</th>
                <th className="text-right px-4 py-3 font-medium">最低库存</th>
                <th className="text-left px-4 py-3 font-medium">位置</th>
                <th className="text-center px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const isLow = item.quantity <= item.min_stock;
                return (
                  <tr key={item.id} className="border-t hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 text-muted-foreground">{item.item_code}</td>
                    <td className="px-4 py-3 font-medium">
                      {item.name}
                      {isLow && <AlertTriangle className="inline h-3.5 w-3.5 text-amber-500 ml-1.5" />}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{item.category}</td>
                    <td className={cn('px-4 py-3 text-right font-medium', isLow && 'text-amber-500')}>
                      {item.quantity} {item.unit || ''}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground">{item.min_stock}</td>
                    <td className="px-4 py-3 text-muted-foreground">{item.location || '-'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" onClick={() => openIO(item, 'in')}>
                          <ArrowDownToLine className="h-3 w-3" /> 入库
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" onClick={() => openIO(item, 'out')}>
                          <ArrowUpFromLine className="h-3 w-3" /> 出库
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新增物料</DialogTitle>
            <DialogDescription>添加新的库存物料</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>物料编码 *</Label>
                <Input placeholder="如 OFF-001" value={form.item_code} onChange={(e) => setForm({ ...form, item_code: e.target.value })} />
              </div>
              <div>
                <Label>物料名称 *</Label>
                <Input placeholder="如 A4打印纸" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>分类</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="office">办公用品</SelectItem>
                    <SelectItem value="hardware">硬件设备</SelectItem>
                    <SelectItem value="material">原材料</SelectItem>
                    <SelectItem value="consumable">耗材</SelectItem>
                    <SelectItem value="other">其他</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>初始数量</Label>
                <Input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
              </div>
              <div>
                <Label>最低库存</Label>
                <Input type="number" value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>存放位置</Label>
                <Input placeholder="如 A区-03柜" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
              </div>
              <div>
                <Label>单位</Label>
                <Input placeholder="如 个/箱/台" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              添加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* In/Out Dialog */}
      <Dialog open={ioDialogOpen} onOpenChange={setIoDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{ioType === 'in' ? '入库' : '出库'} - {selectedItem?.name}</DialogTitle>
            <DialogDescription>当前库存: {selectedItem?.quantity} {selectedItem?.unit || ''}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>数量 *</Label>
              <Input type="number" min={1} value={ioQuantity} onChange={(e) => setIoQuantity(e.target.value)} placeholder="请输入数量" />
            </div>
            <div>
              <Label>备注</Label>
              <Input value={ioReason} onChange={(e) => setIoReason(e.target.value)} placeholder="操作原因（选填）" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIoDialogOpen(false)}>取消</Button>
            <Button onClick={handleIO} disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              确认{ioType === 'in' ? '入库' : '出库'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
