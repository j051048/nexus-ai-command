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
  Award,
  Plus,
  Loader2,
  Search,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Calendar,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface Certificate {
  id: string;
  cert_type: string;
  cert_no: string;
  name: string;
  holder_type: string;
  holder_id?: string;
  issue_date: string;
  expire_date: string;
  status: string;
  created_at: string;
}

const STATUS_MAP: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  valid: { label: '有效', color: 'text-green-600 bg-green-50', icon: CheckCircle2 },
  expiring: { label: '即将到期', color: 'text-amber-600 bg-amber-50', icon: AlertTriangle },
  expired: { label: '已过期', color: 'text-red-600 bg-red-50', icon: XCircle },
  revoked: { label: '已吊销', color: 'text-gray-600 bg-gray-50', icon: XCircle },
};

function getCertStatus(expireDate: string, status: string): string {
  if (status === 'revoked') return 'revoked';
  const now = new Date();
  const expire = new Date(expireDate);
  if (expire < now) return 'expired';
  const diff = (expire.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
  if (diff <= 30) return 'expiring';
  return 'valid';
}

function daysUntilExpiry(expireDate: string): number {
  return Math.ceil((new Date(expireDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

export default function CertificateManagement() {
  const { profile } = useAuth();
  const [certs, setCerts] = useState<Certificate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    cert_type: '',
    cert_no: '',
    name: '',
    holder_type: 'company',
    issue_date: '',
    expire_date: '',
  });

  const orgId = profile?.organization_id;

  const fetchCerts = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      let query = supabase
        .from('certificates')
        .select('*')
        .eq('organization_id', orgId)
        .order('expire_date', { ascending: true });

      if (filterType !== 'all') query = query.eq('cert_type', filterType);
      if (search.trim()) query = query.ilike('name', `%${search.trim()}%`);

      const { data, error } = await query;
      if (error) throw error;
      setCerts((data as Certificate[]) || []);
    } catch (e: any) {
      toast.error('加载证照失败: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, [orgId, filterType, search]);

  useEffect(() => { fetchCerts(); }, [fetchCerts]);

  const handleCreate = async () => {
    if (!form.name.trim() || !form.cert_no.trim() || !form.cert_type.trim()) {
      toast.error('请填写完整的证照信息');
      return;
    }
    setSubmitting(true);
    try {
      const { error } = await supabase.from('certificates').insert({
        cert_type: form.cert_type.trim(),
        cert_no: form.cert_no.trim(),
        name: form.name.trim(),
        holder_type: form.holder_type,
        issue_date: form.issue_date || null,
        expire_date: form.expire_date || null,
        status: 'valid',
        organization_id: orgId,
      });
      if (error) throw error;
      toast.success('证照添加成功');
      setDialogOpen(false);
      setForm({ cert_type: '', cert_no: '', name: '', holder_type: 'company', issue_date: '', expire_date: '' });
      fetchCerts();
    } catch (e: any) {
      toast.error('创建失败: ' + e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const expiringCount = certs.filter((c) => getCertStatus(c.expire_date, c.status) === 'expiring').length;
  const expiredCount = certs.filter((c) => getCertStatus(c.expire_date, c.status) === 'expired').length;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Award className="h-6 w-6" /> 企业证照库
          </h1>
          <p className="text-sm text-muted-foreground mt-1">统一管理企业资质和证照到期预警</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" /> 添加证照
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: '证照总数', value: certs.length, color: '' },
          { label: '有效', value: certs.length - expiringCount - expiredCount, color: 'text-green-500' },
          { label: '即将到期', value: expiringCount, color: 'text-amber-500' },
          { label: '已过期', value: expiredCount, color: 'text-red-500' },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-4 pb-3 px-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className={cn('text-2xl font-bold', s.color)}>{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="搜索证照..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部类型</SelectItem>
            <SelectItem value="business_license">营业执照</SelectItem>
            <SelectItem value="qualification">资质证书</SelectItem>
            <SelectItem value="safety">安全许可</SelectItem>
            <SelectItem value="iso">ISO认证</SelectItem>
            <SelectItem value="other">其他</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Certificate Timeline List */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : certs.length === 0 ? (
        <div className="text-center py-16">
          <Award className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
          <p className="text-muted-foreground">暂无证照记录</p>
        </div>
      ) : (
        <div className="space-y-3">
          {certs.map((cert) => {
            const effectiveStatus = getCertStatus(cert.expire_date, cert.status);
            const st = STATUS_MAP[effectiveStatus] || STATUS_MAP.valid;
            const Icon = st.icon;
            const days = daysUntilExpiry(cert.expire_date);
            return (
              <Card key={cert.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4 flex items-center gap-4">
                  <div className={cn('p-2 rounded-lg', st.color)}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium truncate">{cert.name}</p>
                      <Badge variant="outline" className="text-[10px]">{cert.cert_type}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      编号: {cert.cert_no} &middot; {cert.holder_type === 'company' ? '企业证照' : '个人证照'}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      <span>到期: {cert.expire_date}</span>
                    </div>
                    <p className={cn('text-xs font-medium mt-0.5',
                      effectiveStatus === 'expired' && 'text-red-500',
                      effectiveStatus === 'expiring' && 'text-amber-500',
                      effectiveStatus === 'valid' && 'text-green-500',
                    )}>
                      {effectiveStatus === 'expired' ? `已过期 ${Math.abs(days)} 天` :
                       effectiveStatus === 'expiring' ? `${days} 天后到期` :
                       `剩余 ${days} 天`}
                    </p>
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
            <DialogTitle>添加证照</DialogTitle>
            <DialogDescription>登记企业或个人证照信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>证照名称 *</Label>
              <Input placeholder="如 营业执照" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={100} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>证照类型 *</Label>
                <Input placeholder="如 business_license" value={form.cert_type} onChange={(e) => setForm({ ...form, cert_type: e.target.value })} />
              </div>
              <div>
                <Label>证照编号 *</Label>
                <Input placeholder="证件号码" value={form.cert_no} onChange={(e) => setForm({ ...form, cert_no: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>持有类型</Label>
              <Select value={form.holder_type} onValueChange={(v) => setForm({ ...form, holder_type: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="company">企业</SelectItem>
                  <SelectItem value="employee">个人</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>签发日期</Label>
                <Input type="date" value={form.issue_date} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} />
              </div>
              <div>
                <Label>到期日期</Label>
                <Input type="date" value={form.expire_date} onChange={(e) => setForm({ ...form, expire_date: e.target.value })} />
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
    </div>
  );
}
