import { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
  Package,
  Plus,
  Loader2,
  Search,
  Monitor,
  Armchair,
  Car,
  HardDrive,
  BarChart3,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface Asset {
  id: string;
  asset_code: string;
  name: string;
  asset_type: string;
  status: string;
  value?: number;
  purchase_date?: string;
  department_id?: string;
  created_at: string;
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  idle: { label: '闲置', color: 'bg-gray-100 text-gray-700' },
  in_use: { label: '使用中', color: 'bg-green-100 text-green-700' },
  maintenance: { label: '维修中', color: 'bg-amber-100 text-amber-700' },
  scrapped: { label: '已报废', color: 'bg-red-100 text-red-700' },
};

const TYPE_ICONS: Record<string, React.ElementType> = {
  computer: Monitor,
  furniture: Armchair,
  vehicle: Car,
  server: HardDrive,
};

export default function AssetManagement() {
  const { profile } = useAuth();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    asset_code: '',
    name: '',
    asset_type: 'computer',
    value: '',
  });

  const orgId = profile?.organization_id;

  const fetchAssets = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      let query = supabase
        .from('assets')
        .select('*')
        .eq('organization_id', orgId)
        .order('created_at', { ascending: false });

      if (filterStatus !== 'all') query = query.eq('status', filterStatus);
      if (search.trim()) query = query.ilike('name', `%${search.trim()}%`);

      const { data, error } = await query;
      if (error) throw error;
      setAssets((data as Asset[]) || []);
    } catch (e: any) {
      toast.error('加载资产失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, [orgId, filterStatus, search]);

  useEffect(() => { fetchAssets(); }, [fetchAssets]);

  const handleCreate = async () => {
    if (!form.asset_code.trim() || !form.name.trim()) {
      toast.error('资产编号和名称不能为空');
      return;
    }
    setSubmitting(true);
    try {
      const { error } = await supabase.from('assets').insert({
        asset_code: form.asset_code.trim(),
        name: form.name.trim(),
        asset_type: form.asset_type,
        value: form.value ? Number(form.value) : null,
        status: 'idle',
        organization_id: orgId,
      });
      if (error) throw error;
      toast.success('资产登记成功');
      setDialogOpen(false);
      setForm({ asset_code: '', name: '', asset_type: 'computer', value: '' });
      fetchAssets();
    } catch (e: any) {
      toast.error('创建失败: ' + e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const stats = {
    total: assets.length,
    in_use: assets.filter((a) => a.status === 'in_use').length,
    idle: assets.filter((a) => a.status === 'idle').length,
    totalValue: assets.reduce((sum, a) => sum + (a.value || 0), 0),
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Package className="h-6 w-6" /> 资产管理
          </h1>
          <p className="text-sm text-muted-foreground mt-1">管理企业固定资产全生命周期</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" /> 资产入库
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '资产总数', value: stats.total },
          { label: '使用中', value: stats.in_use },
          { label: '闲置', value: stats.idle },
          { label: '总价值', value: `${(stats.totalValue / 10000).toFixed(1)}万` },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-4 pb-3 px-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className="text-2xl font-bold">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="搜索资产..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[130px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            {Object.entries(STATUS_MAP).map(([k, v]) => (
              <SelectItem key={k} value={k}>{v.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Asset List */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : assets.length === 0 ? (
        <div className="text-center py-16">
          <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
          <p className="text-muted-foreground">暂无资产记录</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {assets.map((asset) => {
            const st = STATUS_MAP[asset.status] || STATUS_MAP.idle;
            const Icon = TYPE_ICONS[asset.asset_type] || Package;
            return (
              <Card key={asset.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium">{asset.name}</p>
                        <p className="text-xs text-muted-foreground">{asset.asset_code}</p>
                      </div>
                    </div>
                    <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', st.color)}>
                      {st.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{asset.asset_type}</span>
                    {asset.value != null && <span>{asset.value.toLocaleString()} 元</span>}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>资产入库</DialogTitle>
            <DialogDescription>登记新的固定资产</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>资产编号 *</Label>
              <Input placeholder="如 IT-2026-001" value={form.asset_code} onChange={(e) => setForm({ ...form, asset_code: e.target.value })} maxLength={50} />
            </div>
            <div>
              <Label>资产名称 *</Label>
              <Input placeholder="如 MacBook Pro 16寸" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={100} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>类型</Label>
                <Select value={form.asset_type} onValueChange={(v) => setForm({ ...form, asset_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="computer">电脑设备</SelectItem>
                    <SelectItem value="furniture">办公家具</SelectItem>
                    <SelectItem value="vehicle">车辆</SelectItem>
                    <SelectItem value="server">服务器</SelectItem>
                    <SelectItem value="other">其他</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>价值 (元)</Label>
                <Input type="number" placeholder="0" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              登记入库
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
