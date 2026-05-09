import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock,
  Copy,
  CreditCard,
  FileText,
  QrCode,
  Receipt,
  RefreshCw,
  Smartphone,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';

import { aiClient } from '@/api/aiClient';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

type PaymentMethod = {
  id: string;
  name: string;
  description: string;
  available: boolean;
};

type PaymentOrder = {
  id: string;
  order_no: string;
  plan_id: string;
  plan_name?: string;
  payment_method: string;
  amount: number;
  status: string;
  invoice_status?: string;
  created_at: string;
};

type BankInfo = {
  bank_name: string;
  branch: string;
  account_name: string;
  account_number: string;
  reference: string;
  note: string;
  configured?: boolean;
};

const PLANS = [
  { id: 'starter', name: '基础版', price: 199, yearly: 1990, features: ['基础管理功能', '文档管理', '邮件支持'] },
  {
    id: 'professional',
    name: '专业版',
    price: 699,
    yearly: 6990,
    features: ['核心业务模块', '优先支持', 'API 访问', '组织权限管理'],
    popular: true,
  },
  { id: 'enterprise', name: '企业版', price: 1999, yearly: 19990, features: ['全部核心能力', 'SLA 保障', '专属支持', 'SSO', '定制集成'] },
];

const FALLBACK_METHODS: PaymentMethod[] = [
  { id: 'bank_transfer', name: '对公转账', description: '银行对公转账，首发推荐方式', available: true },
  { id: 'wechat_pay', name: '微信支付', description: '真实通道接入后开放', available: false },
  { id: 'alipay', name: '支付宝', description: '真实通道接入后开放', available: false },
];

const methodIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  bank_transfer: Building2,
  wechat_pay: Smartphone,
  alipay: QrCode,
};

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: '待支付', color: 'text-yellow-600 bg-yellow-500/10', icon: <Clock className="h-4 w-4" /> },
  paid: { label: '已支付', color: 'text-green-600 bg-green-500/10', icon: <CheckCircle2 className="h-4 w-4" /> },
  cancelled: { label: '已取消', color: 'text-muted-foreground bg-muted', icon: <XCircle className="h-4 w-4" /> },
  refunded: { label: '已退款', color: 'text-blue-600 bg-blue-500/10', icon: <RefreshCw className="h-4 w-4" /> },
  failed: { label: '失败', color: 'text-red-600 bg-red-500/10', icon: <XCircle className="h-4 w-4" /> },
};

export default function PaymentPage() {
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState('bank_transfer');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [methods, setMethods] = useState<PaymentMethod[]>(FALLBACK_METHODS);
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const [bankInfo, setBankInfo] = useState<BankInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [invoiceDialogOpen, setInvoiceDialogOpen] = useState(false);
  const [invoiceOrderId, setInvoiceOrderId] = useState('');
  const [invoiceForm, setInvoiceForm] = useState({
    company_name: '',
    tax_number: '',
    address: '',
    phone: '',
    bank: '',
    account: '',
  });

  const selectedPlanInfo = useMemo(() => PLANS.find((plan) => plan.id === selectedPlan), [selectedPlan]);

  useEffect(() => {
    void fetchMethods();
    void fetchOrders();
  }, []);

  const fetchMethods = async () => {
    try {
      const res = await aiClient.fetch<{ data: { methods: PaymentMethod[] } }>('api/payments/methods', { _silentError: true });
      if (res.data?.methods?.length) setMethods(res.data.methods);
    } catch {
      setMethods(FALLBACK_METHODS);
    }
  };

  const fetchOrders = async () => {
    setOrdersLoading(true);
    try {
      const res = await aiClient.fetch<{ data: PaymentOrder[] }>('api/payments/orders', { _silentError: true });
      setOrders(Array.isArray(res.data) ? res.data : []);
    } catch {
      setOrders([]);
    } finally {
      setOrdersLoading(false);
    }
  };

  const fetchBankInfo = async (planId: string) => {
    try {
      const res = await aiClient.fetch<{ data: { bank_info: BankInfo } }>(`api/payments/bank-info?plan_id=${planId}`);
      setBankInfo(res.data.bank_info);
    } catch {
      setBankInfo(null);
    }
  };

  const handleCreateOrder = async () => {
    if (!selectedPlanInfo) {
      toast.error('请先选择订阅计划');
      return;
    }

    const method = methods.find((item) => item.id === selectedMethod);
    if (!method?.available) {
      toast.error('该支付方式尚未开放');
      return;
    }

    const amount = billingCycle === 'monthly' ? selectedPlanInfo.price : selectedPlanInfo.yearly;
    setLoading(true);
    try {
      const res = await aiClient.fetch<{ data: { order: PaymentOrder } }>('api/payments/create-order', {
        method: 'POST',
        body: JSON.stringify({ plan_id: selectedPlan, payment_method: selectedMethod, amount }),
      });
      toast.success(`订单已创建：${res.data.order.order_no}`);
      await fetchOrders();
      if (selectedMethod === 'bank_transfer') await fetchBankInfo(selectedPlan);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '创建订单失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => toast.success('已复制'));
  };

  const handleInvoice = async () => {
    if (!invoiceForm.company_name || !invoiceForm.tax_number) {
      toast.error('请填写完整的发票信息');
      return;
    }
    try {
      await aiClient.fetch('api/payments/invoice', {
        method: 'POST',
        body: JSON.stringify({ order_id: invoiceOrderId, invoice_info: invoiceForm }),
      });
      toast.success('发票申请已提交');
      setInvoiceDialogOpen(false);
      await fetchOrders();
    } catch {
      toast.error('发票申请失败');
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">订阅与支付</h1>
        <p className="text-muted-foreground">首发生产环境仅开放对公转账，微信/支付宝将在真实通道完成后启用。</p>
      </div>

      <div className="flex items-center justify-center gap-3">
        <Button variant={billingCycle === 'monthly' ? 'default' : 'outline'} size="sm" onClick={() => setBillingCycle('monthly')}>
          月付
        </Button>
        <Button variant={billingCycle === 'yearly' ? 'default' : 'outline'} size="sm" onClick={() => setBillingCycle('yearly')}>
          年付
          <Badge variant="secondary" className="ml-2 text-xs">省 17%</Badge>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {PLANS.map((plan) => {
          const price = billingCycle === 'monthly' ? plan.price : plan.yearly;
          const isSelected = selectedPlan === plan.id;
          return (
            <Card
              key={plan.id}
              className={cn('relative cursor-pointer transition-all hover:shadow-md', isSelected && 'ring-2 ring-primary', plan.popular && 'border-primary')}
              onClick={() => setSelectedPlan(plan.id)}
            >
              {plan.popular && <Badge className="absolute -top-2 left-1/2 -translate-x-1/2">推荐</Badge>}
              <CardHeader className="text-center">
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>
                  <span className="text-3xl font-bold text-foreground">¥{price.toLocaleString()}</span>
                  <span>/{billingCycle === 'monthly' ? '月' : '年'}</span>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm">
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {selectedPlan && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">选择支付方式</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              {methods.map((method) => {
                const Icon = methodIcons[method.id] || CreditCard;
                return (
                  <button
                    key={method.id}
                    type="button"
                    className={cn(
                      'flex items-center gap-3 rounded-lg border p-4 text-left transition-all',
                      selectedMethod === method.id && 'bg-primary/5 ring-2 ring-primary',
                      !method.available && 'cursor-not-allowed opacity-50',
                    )}
                    onClick={() => method.available && setSelectedMethod(method.id)}
                  >
                    <Icon className="h-8 w-8 text-muted-foreground" />
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{method.name}</span>
                      <span className="block text-xs text-muted-foreground">{method.description}</span>
                    </span>
                    {!method.available && <Badge variant="outline">未开放</Badge>}
                  </button>
                );
              })}
            </div>

            <Separator />

            {selectedMethod === 'bank_transfer' && bankInfo && (
              <div className="space-y-3 rounded-lg bg-muted/50 p-4">
                <h4 className="flex items-center gap-2 font-medium">
                  <Building2 className="h-5 w-5" />
                  对公转账信息
                </h4>
                {!bankInfo.configured && (
                  <p className="rounded-md bg-yellow-500/10 px-3 py-2 text-sm text-yellow-700">
                    银行账户尚未完整配置，请在生产环境补齐 BANK_NAME、BANK_BRANCH、BANK_ACCOUNT_NAME、BANK_ACCOUNT_NUMBER。
                  </p>
                )}
                {[
                  { label: '开户银行', value: bankInfo.bank_name },
                  { label: '支行', value: bankInfo.branch },
                  { label: '户名', value: bankInfo.account_name },
                  { label: '账号', value: bankInfo.account_number },
                  { label: '转账备注', value: bankInfo.reference },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between gap-3">
                    <span className="text-sm text-muted-foreground">{item.label}</span>
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate font-mono text-sm">{item.value}</span>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => copyToClipboard(String(item.value))}>
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
                <p className="text-xs text-muted-foreground">{bankInfo.note}</p>
              </div>
            )}

            <Button className="w-full gap-2" onClick={handleCreateOrder} disabled={loading || selectedMethod !== 'bank_transfer'}>
              {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
              生成转账订单
              <ArrowRight className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <FileText className="h-5 w-5" />
            我的订单
          </CardTitle>
        </CardHeader>
        <CardContent>
          {ordersLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((item) => <Skeleton key={item} className="h-16 w-full" />)}
            </div>
          ) : orders.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">暂无订单</p>
          ) : (
            <div className="space-y-3">
              {orders.map((order) => {
                const status = statusConfig[order.status] || statusConfig.pending;
                return (
                  <div key={order.id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">{order.plan_name || order.plan_id}</span>
                        <Badge className={cn('gap-1', status.color)}>{status.icon}{status.label}</Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        订单号 {order.order_no} | {new Date(order.created_at).toLocaleDateString('zh-CN')}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="font-bold">¥{Number(order.amount).toLocaleString()}</span>
                      {order.status === 'paid' && !['requested', 'issued'].includes(order.invoice_status || '') && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1"
                          onClick={() => {
                            setInvoiceOrderId(order.id);
                            setInvoiceDialogOpen(true);
                          }}
                        >
                          <Receipt className="h-3.5 w-3.5" />
                          开票
                        </Button>
                      )}
                      {order.invoice_status === 'requested' && <Badge variant="outline">开票中</Badge>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={invoiceDialogOpen} onOpenChange={setInvoiceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>申请增值税发票</DialogTitle>
            <DialogDescription>请填写完整的开票信息，提交后由财务审核处理。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>公司名称 *</Label>
              <Input value={invoiceForm.company_name} onChange={(event) => setInvoiceForm({ ...invoiceForm, company_name: event.target.value })} placeholder="请输入公司全称" />
            </div>
            <div className="space-y-2">
              <Label>税号 *</Label>
              <Input value={invoiceForm.tax_number} onChange={(event) => setInvoiceForm({ ...invoiceForm, tax_number: event.target.value })} placeholder="请输入纳税人识别号" />
            </div>
            <div className="space-y-2">
              <Label>地址</Label>
              <Input value={invoiceForm.address} onChange={(event) => setInvoiceForm({ ...invoiceForm, address: event.target.value })} placeholder="公司注册地址，选填" />
            </div>
            <div className="space-y-2">
              <Label>电话</Label>
              <Input value={invoiceForm.phone} onChange={(event) => setInvoiceForm({ ...invoiceForm, phone: event.target.value })} placeholder="公司电话，选填" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>开户银行</Label>
                <Input value={invoiceForm.bank} onChange={(event) => setInvoiceForm({ ...invoiceForm, bank: event.target.value })} placeholder="选填" />
              </div>
              <div className="space-y-2">
                <Label>银行账号</Label>
                <Input value={invoiceForm.account} onChange={(event) => setInvoiceForm({ ...invoiceForm, account: event.target.value })} placeholder="选填" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvoiceDialogOpen(false)}>取消</Button>
            <Button onClick={handleInvoice}>提交申请</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
