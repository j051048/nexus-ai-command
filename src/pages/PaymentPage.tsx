/**
 * 国内支付页面
 * 支持对公转账（主要）、微信支付、支付宝
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import {
  Building2,
  Smartphone,
  QrCode,
  Copy,
  CheckCircle2,
  Clock,
  XCircle,
  FileText,
  CreditCard,
  ArrowRight,
  RefreshCw,
  Receipt,
} from 'lucide-react';
import { aiClient } from '@/api/aiClient';
import { toast } from 'sonner';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyData = Record<string, any>;

// 订阅计划
const PLANS = [
  { id: 'starter', name: '基础版', price: 199, yearly: 1990, features: ['基础对话', '文档管理', '邮件支持'] },
  { id: 'professional', name: '专业版', price: 699, yearly: 6990, features: ['全部功能', '优先支持', 'API 访问', '自定义工具'], popular: true },
  { id: 'enterprise', name: '企业版', price: 1999, yearly: 19990, features: ['全部功能', 'SLA 保障', '专属支持', 'SSO', '自定义集成'] },
];

// 支付方式
const PAYMENT_METHODS = [
  { id: 'bank_transfer', name: '对公转账', icon: Building2, description: '银行对公转账（推荐）', available: true },
  { id: 'wechat_pay', name: '微信支付', icon: Smartphone, description: '微信扫码支付', available: false },
  { id: 'alipay', name: '支付宝', icon: QrCode, description: '支付宝扫码支付', available: false },
];

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: '待支付', color: 'text-yellow-500 bg-yellow-500/10', icon: <Clock className="w-4 h-4" /> },
  paid: { label: '已支付', color: 'text-green-500 bg-green-500/10', icon: <CheckCircle2 className="w-4 h-4" /> },
  cancelled: { label: '已取消', color: 'text-muted-foreground bg-muted', icon: <XCircle className="w-4 h-4" /> },
  refunded: { label: '已退款', color: 'text-blue-500 bg-blue-500/10', icon: <RefreshCw className="w-4 h-4" /> },
  failed: { label: '失败', color: 'text-red-500 bg-red-500/10', icon: <XCircle className="w-4 h-4" /> },
};

function PaymentPage() {
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState('bank_transfer');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const [orders, setOrders] = useState<AnyData[]>([]);
  const [bankInfo, setBankInfo] = useState<AnyData | null>(null);
  const [loading, setLoading] = useState(false);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [invoiceDialogOpen, setInvoiceDialogOpen] = useState(false);
  const [invoiceOrderId, setInvoiceOrderId] = useState('');
  const [invoiceForm, setInvoiceForm] = useState({ company_name: '', tax_number: '', address: '', phone: '', bank: '', account: '' });

  // 获取订单列表
  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    setOrdersLoading(true);
    try {
      const res = await aiClient.fetch<{ success: boolean; data: AnyData[] }>('api/payments/orders');
      setOrders(res.data || []);
    } catch {
      // 使用模拟数据
      setOrders([]);
    } finally {
      setOrdersLoading(false);
    }
  };

  // 获取对公转账信息
  const fetchBankInfo = async (planId: string) => {
    try {
      const res = await aiClient.fetch<{ success: boolean; data: { bank_info: AnyData } }>(
        `api/payments/bank-info?plan_id=${planId}`
      );
      setBankInfo(res.data.bank_info);
    } catch {
      setBankInfo({
        bank_name: '中国工商银行',
        branch: '北京市海淀区中关村支行',
        account_name: 'Nexus AI 科技有限公司',
        account_number: '待配置',
        reference: 'ORG-XXXXXXXX',
        note: '请在转账备注中填写参考号',
      });
    }
  };

  // 创建订单
  const handleCreateOrder = async () => {
    if (!selectedPlan) {
      toast.error('请先选择订阅计划');
      return;
    }

    const plan = PLANS.find(p => p.id === selectedPlan);
    if (!plan) return;

    const amount = billingCycle === 'monthly' ? plan.price : plan.yearly;

    setLoading(true);
    try {
      const res = await aiClient.fetch<{ success: boolean; data: { order: AnyData } }>(
        'api/payments/create-order',
        {
          method: 'POST',
          body: JSON.stringify({
            plan_id: selectedPlan,
            payment_method: selectedMethod,
            amount,
          }),
        }
      );
      toast.success(`订单已创建: ${res.data.order.order_no}`);
      fetchOrders();

      if (selectedMethod === 'bank_transfer') {
        fetchBankInfo(selectedPlan);
      }
    } catch (err) {
      toast.error('创建订单失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 复制到剪贴板
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => toast.success('已复制'));
  };

  // 申请发票
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
    } catch {
      toast.error('发票申请失败');
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold">订阅支付</h1>
        <p className="text-muted-foreground">选择订阅计划并完成支付</p>
      </div>

      {/* 计费周期切换 */}
      <div className="flex items-center justify-center gap-4">
        <Button
          variant={billingCycle === 'monthly' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setBillingCycle('monthly')}
        >
          月付
        </Button>
        <Button
          variant={billingCycle === 'yearly' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setBillingCycle('yearly')}
        >
          年付
          <Badge variant="secondary" className="ml-2 text-xs">省 17%</Badge>
        </Button>
      </div>

      {/* 计划选择 */}
      <div className="grid md:grid-cols-3 gap-4">
        {PLANS.map(plan => {
          const price = billingCycle === 'monthly' ? plan.price : plan.yearly;
          const isSelected = selectedPlan === plan.id;
          return (
            <Card
              key={plan.id}
              className={cn(
                'cursor-pointer transition-all hover:shadow-md relative',
                isSelected && 'ring-2 ring-primary',
                plan.popular && 'border-primary'
              )}
              onClick={() => setSelectedPlan(plan.id)}
            >
              {plan.popular && (
                <Badge className="absolute -top-2 left-1/2 -translate-x-1/2">最受欢迎</Badge>
              )}
              <CardHeader className="text-center">
                <CardTitle>{plan.name}</CardTitle>
                <div className="mt-2">
                  <span className="text-3xl font-bold">{'\u00A5'}{price}</span>
                  <span className="text-muted-foreground">/{billingCycle === 'monthly' ? '月' : '年'}</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {plan.features.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* 支付方式 */}
      {selectedPlan && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">选择支付方式</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-3 gap-3">
              {PAYMENT_METHODS.map(method => (
                <div
                  key={method.id}
                  className={cn(
                    'flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-all',
                    selectedMethod === method.id && 'ring-2 ring-primary bg-primary/5',
                    !method.available && 'opacity-50'
                  )}
                  onClick={() => method.available && setSelectedMethod(method.id)}
                >
                  <method.icon className="w-8 h-8 text-muted-foreground" />
                  <div>
                    <p className="font-medium">{method.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {method.available ? method.description : '即将上线'}
                    </p>
                  </div>
                  {!method.available && (
                    <Badge variant="outline" className="ml-auto text-xs">即将上线</Badge>
                  )}
                </div>
              ))}
            </div>

            <Separator />

            {/* 对公转账信息 */}
            {selectedMethod === 'bank_transfer' && bankInfo && (
              <div className="bg-muted/50 rounded-lg p-4 space-y-3">
                <h4 className="font-medium flex items-center gap-2">
                  <Building2 className="w-5 h-5" />
                  对公转账信息
                </h4>
                {[
                  { label: '开户银行', value: bankInfo.bank_name },
                  { label: '支行', value: bankInfo.branch },
                  { label: '户名', value: bankInfo.account_name },
                  { label: '账号', value: bankInfo.account_number },
                  { label: '转账备注', value: bankInfo.reference },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono">{item.value}</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => copyToClipboard(String(item.value))}
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                ))}
                <p className="text-xs text-muted-foreground mt-2">{bankInfo.note}</p>
              </div>
            )}

            {/* 微信/支付宝占位 */}
            {(selectedMethod === 'wechat_pay' || selectedMethod === 'alipay') && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <QrCode className="w-16 h-16 text-muted-foreground mb-4" />
                <h4 className="font-medium text-lg">
                  {selectedMethod === 'wechat_pay' ? '微信支付' : '支付宝'}即将上线
                </h4>
                <p className="text-sm text-muted-foreground mt-2">
                  扫码支付功能正在对接中，请先使用对公转账方式
                </p>
              </div>
            )}

            <Button
              className="w-full gap-2"
              onClick={handleCreateOrder}
              disabled={loading || !selectedMethod || selectedMethod !== 'bank_transfer'}
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
              {selectedMethod === 'bank_transfer' ? '生成转账订单' : '暂不可用'}
              <ArrowRight className="w-4 h-4" />
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 订单列表 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <FileText className="w-5 h-5" />
            我的订单
          </CardTitle>
        </CardHeader>
        <CardContent>
          {ordersLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : orders.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">暂无订单</p>
          ) : (
            <div className="space-y-3">
              {orders.map((order, idx) => {
                const status = statusConfig[order.status] || statusConfig.pending;
                return (
                  <div key={order.id || idx} className="flex items-center justify-between p-3 rounded-lg border">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{order.plan_name || order.plan_id}</span>
                        <Badge className={cn('gap-1', status.color)}>
                          {status.icon}
                          {status.label}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        订单号: {order.order_no} | {new Date(order.created_at).toLocaleDateString('zh-CN')}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-bold">{'\u00A5'}{Number(order.amount).toLocaleString()}</span>
                      {order.status === 'paid' && order.invoice_status !== 'requested' && order.invoice_status !== 'issued' && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1"
                          onClick={() => {
                            setInvoiceOrderId(order.id);
                            setInvoiceDialogOpen(true);
                          }}
                        >
                          <Receipt className="w-3 h-3" />
                          开票
                        </Button>
                      )}
                      {order.invoice_status === 'requested' && (
                        <Badge variant="outline">开票中</Badge>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 发票申请弹窗 */}
      <Dialog open={invoiceDialogOpen} onOpenChange={setInvoiceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>申请增值税发票</DialogTitle>
            <DialogDescription>请填写完整的开票信息</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>公司名称 *</Label>
              <Input
                value={invoiceForm.company_name}
                onChange={e => setInvoiceForm({ ...invoiceForm, company_name: e.target.value })}
                placeholder="请输入公司全称"
              />
            </div>
            <div className="space-y-2">
              <Label>税号 *</Label>
              <Input
                value={invoiceForm.tax_number}
                onChange={e => setInvoiceForm({ ...invoiceForm, tax_number: e.target.value })}
                placeholder="请输入纳税人识别号"
              />
            </div>
            <div className="space-y-2">
              <Label>地址</Label>
              <Input
                value={invoiceForm.address}
                onChange={e => setInvoiceForm({ ...invoiceForm, address: e.target.value })}
                placeholder="公司注册地址（选填）"
              />
            </div>
            <div className="space-y-2">
              <Label>电话</Label>
              <Input
                value={invoiceForm.phone}
                onChange={e => setInvoiceForm({ ...invoiceForm, phone: e.target.value })}
                placeholder="公司电话（选填）"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>开户银行</Label>
                <Input
                  value={invoiceForm.bank}
                  onChange={e => setInvoiceForm({ ...invoiceForm, bank: e.target.value })}
                  placeholder="选填"
                />
              </div>
              <div className="space-y-2">
                <Label>银行账号</Label>
                <Input
                  value={invoiceForm.account}
                  onChange={e => setInvoiceForm({ ...invoiceForm, account: e.target.value })}
                  placeholder="选填"
                />
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

export default PaymentPage;
