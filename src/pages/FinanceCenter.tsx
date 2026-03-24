import { useState, useEffect, useCallback } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
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
  Receipt,
  FileText,
  PiggyBank,
  DollarSign,
  Clock,
  CheckCircle2,
  XCircle,
  Plus,
  Loader2,
  Wallet,
  Pencil,
  Trash2,
} from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useMyApprovals, useSubmitApproval } from '@/hooks/useApprovals';
import { supabase } from '@/integrations/supabase/client';
import { toast } from 'sonner';

// Local interface for finance_budgets (not in types.ts)
interface FinanceBudget {
  id: string;
  organization_id: string;
  department_id?: string;
  project_id?: string;
  name: string;
  total_amount: number;
  used_amount: number;
  period: string;
  created_at: string;
}

// Local interface for finance_invoices rows
interface FinanceInvoice {
  id: string;
  organization_id: string;
  invoice_number: string;
  amount: number;
  status: string;
  due_date: string | null;
  customer_id: string | null;
  created_at: string;
}

function FinanceApprovalBanner() {
  const navigate = useNavigate();
  return (
    <div className="flex items-center justify-between bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3 border border-amber-200 dark:border-amber-800">
      <span className="text-sm text-amber-700 dark:text-amber-300">
        报销审批已纳入统一审批中心，可在审批中心查看所有审批进度
      </span>
      <Button variant="link" size="sm" className="text-amber-600" onClick={() => navigate('/approval')}>
        前往审批中心 →
      </Button>
    </div>
  );
}

export function FinanceCenter() {
  const { user, profile } = useAuth();
  const [activeTab, setActiveTab] = useState('expense');

  // --- Expense tab (reuse existing hooks) ---
  const { data: myApprovals, isLoading: expenseLoading } = useMyApprovals();
  const submitApproval = useSubmitApproval();

  const expenseRecords = (myApprovals || []).filter(
    (a) => a.type === 'expense' || a.type === 'travel' || a.type === 'purchase'
  );

  const expenseStats = {
    totalAmount: expenseRecords
      .filter((a) => a.status === 'approved')
      .reduce((sum, a) => sum + (a.amount || 0), 0),
    pending: expenseRecords.filter((a) => a.status === 'pending').length,
    rejected: expenseRecords.filter((a) => a.status === 'rejected').length,
    total: expenseRecords.length,
  };

  // --- New expense dialog ---
  const [expenseDialogOpen, setExpenseDialogOpen] = useState(false);
  const [expenseFilter, setExpenseFilter] = useState('all');
  const [expenseForm, setExpenseForm] = useState({
    type: 'expense',
    description: '',
    amount: 0,
  });
  const [submitting, setSubmitting] = useState(false);

  // --- New budget dialog ---
  const [budgetDialogOpen, setBudgetDialogOpen] = useState(false);
  const [editingBudgetId, setEditingBudgetId] = useState<string | null>(null);
  const [budgetForm, setBudgetForm] = useState({
    name: '',
    total_amount: 0,
    period: new Date().toISOString().slice(0, 7),
  });
  const [budgetSubmitting, setBudgetSubmitting] = useState(false);

  // --- New invoice dialog ---
  const [invoiceDialogOpen, setInvoiceDialogOpen] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState({
    invoice_number: '',
    amount: 0,
    due_date: '',
    status: 'draft',
  });
  const [invoiceSubmitting, setInvoiceSubmitting] = useState(false);

  const handleSubmitExpense = async () => {
    if (!expenseForm.description.trim()) {
      toast.error('请填写报销说明');
      return;
    }
    if (expenseForm.amount <= 0) {
      toast.error('请输入有效金额');
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitApproval.mutateAsync({
        type: expenseForm.type,
        description: expenseForm.description,
        amount: expenseForm.amount,
      });
      if (result.status === 'approved') {
        toast.success('金额较小，已自动审批通过');
      } else {
        toast.success('报销申请已提交，等待审批');
      }
      setExpenseDialogOpen(false);
      setExpenseForm({ type: 'expense', description: '', amount: 0 });
    } catch (error: unknown) {
      toast.error((error instanceof Error ? error.message : null) || '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitBudget = async () => {
    if (!budgetForm.name.trim()) {
      toast.error('请填写预算名称');
      return;
    }
    if (budgetForm.total_amount <= 0) {
      toast.error('请输入有效金额');
      return;
    }
    setBudgetSubmitting(true);
    try {
      if (editingBudgetId) {
        const { error } = await supabase.from('finance_budgets')
          .update({
            name: budgetForm.name,
            total_amount: budgetForm.total_amount,
            period: budgetForm.period,
          })
          .eq('id', editingBudgetId);
        if (error) throw error;
        toast.success('预算更新成功');
      } else {
        const { error } = await supabase.from('finance_budgets').insert({
          name: budgetForm.name,
          total_amount: budgetForm.total_amount,
          used_amount: 0,
          period: budgetForm.period,
          organization_id: profile?.organization_id,
        });
        if (error) throw error;
        toast.success('预算创建成功');
      }
      setBudgetDialogOpen(false);
      setEditingBudgetId(null);
      setBudgetForm({ name: '', total_amount: 0, period: new Date().toISOString().slice(0, 7) });
      fetchBudgets();
    } catch (error: unknown) {
      toast.error((error instanceof Error ? error.message : null) || '操作失败');
    } finally {
      setBudgetSubmitting(false);
    }
  };

  const handleEditBudget = (budget: FinanceBudget) => {
    setEditingBudgetId(budget.id);
    setBudgetForm({
      name: budget.name,
      total_amount: budget.total_amount,
      period: budget.period,
    });
    setBudgetDialogOpen(true);
  };

  const handleDeleteBudget = async (budgetId: string) => {
    if (!window.confirm('确认删除此预算？删除后不可恢复。')) return;
    try {
      const { error } = await supabase.from('finance_budgets')
        .delete()
        .eq('id', budgetId);
      if (error) throw error;
      toast.success('预算已删除');
      fetchBudgets();
    } catch (error: unknown) {
      toast.error((error instanceof Error ? error.message : null) || '删除失败');
    }
  };

  const handleSubmitInvoice = async () => {
    if (!invoiceForm.invoice_number.trim()) {
      toast.error('请填写发票号');
      return;
    }
    if (invoiceForm.amount <= 0) {
      toast.error('请输入有效金额');
      return;
    }
    setInvoiceSubmitting(true);
    try {
      const { error } = await supabase.from('finance_invoices').insert({
        invoice_number: invoiceForm.invoice_number,
        amount: invoiceForm.amount,
        due_date: invoiceForm.due_date || null,
        status: invoiceForm.status,
        organization_id: profile?.organization_id,
      });
      if (error) throw error;
      toast.success('发票创建成功');
      setInvoiceDialogOpen(false);
      setInvoiceForm({ invoice_number: '', amount: 0, due_date: '', status: 'draft' });
      fetchInvoices();
    } catch (error: unknown) {
      toast.error((error instanceof Error ? error.message : null) || '创建失败');
    } finally {
      setInvoiceSubmitting(false);
    }
  };

  // --- Invoice tab ---
  const [invoices, setInvoices] = useState<FinanceInvoice[]>([]);
  const [invoiceLoading, setInvoiceLoading] = useState(true);

  const fetchInvoices = useCallback(async () => {
    try {
      if (!profile?.organization_id) return;
      const { data, error } = await supabase
        .from('finance_invoices')
        .select('*')
        .eq('organization_id', profile.organization_id)
        .order('created_at', { ascending: false });
      if (error) throw error;
      setInvoices((data as FinanceInvoice[]) || []);
    } catch (error: unknown) {
      toast.error('加载发票数据失败');
    } finally {
      setInvoiceLoading(false);
    }
  }, [profile?.organization_id]);

  // --- Budget tab ---
  const [budgets, setBudgets] = useState<FinanceBudget[]>([]);
  const [budgetLoading, setBudgetLoading] = useState(true);

  const fetchBudgets = useCallback(async () => {
    try {
      if (!profile?.organization_id) return;
      const { data, error } = await supabase.from('finance_budgets')
        .select('*')
        .eq('organization_id', profile.organization_id)
        .order('created_at', { ascending: false });
      if (error) throw error;
      setBudgets((data as FinanceBudget[]) || []);
    } catch (error: unknown) {
      toast.error('加载预算数据失败');
    } finally {
      setBudgetLoading(false);
    }
  }, [profile?.organization_id]);

  useEffect(() => {
    fetchInvoices();
    fetchBudgets();
  }, [fetchInvoices, fetchBudgets]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return <Badge className="bg-green-500/10 text-green-600 border-green-200">已通过</Badge>;
      case 'rejected':
        return <Badge className="bg-red-500/10 text-red-600 border-red-200">已拒绝</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-500/10 text-yellow-600 border-yellow-200">待审批</Badge>;
      case 'paid':
        return <Badge className="bg-green-500/10 text-green-600 border-green-200">已付款</Badge>;
      case 'overdue':
        return <Badge className="bg-red-500/10 text-red-600 border-red-200">已逾期</Badge>;
      case 'draft':
        return <Badge className="bg-gray-500/10 text-gray-600 border-gray-200">草稿</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getExpenseTypeLabel = (type: string) => {
    switch (type) {
      case 'expense': return '日常报销';
      case 'travel': return '差旅报销';
      case 'purchase': return '采购申请';
      default: return type;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold">财务中心</h1>
          <p className="text-muted-foreground">管理报销申请、发票和预算</p>
        </div>
        <Button onClick={() => setExpenseDialogOpen(true)} className="gap-2">
          <Plus className="w-4 h-4" />
          新建报销
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="expense" className="gap-2">
            <Receipt className="w-4 h-4" />
            报销管理
          </TabsTrigger>
          <TabsTrigger value="invoice" className="gap-2">
            <FileText className="w-4 h-4" />
            发票管理
          </TabsTrigger>
          <TabsTrigger value="budget" className="gap-2">
            <PiggyBank className="w-4 h-4" />
            预算概览
          </TabsTrigger>
        </TabsList>

        {/* 报销管理 */}
        <TabsContent value="expense" className="space-y-4">
          {/* 审批中心引导横幅 */}
          <FinanceApprovalBanner />
          {/* 统计卡片 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">已报销金额</p>
                    <p className="text-2xl font-bold">{expenseStats.totalAmount.toLocaleString()}</p>
                  </div>
                  <div className="p-3 rounded-full bg-green-500/10">
                    <DollarSign className="w-6 h-6 text-green-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">待审批</p>
                    <p className="text-2xl font-bold text-yellow-500">{expenseStats.pending}</p>
                  </div>
                  <div className="p-3 rounded-full bg-yellow-500/10">
                    <Clock className="w-6 h-6 text-yellow-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">已拒绝</p>
                    <p className="text-2xl font-bold text-red-500">{expenseStats.rejected}</p>
                  </div>
                  <div className="p-3 rounded-full bg-red-500/10">
                    <XCircle className="w-6 h-6 text-red-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">总申请数</p>
                    <p className="text-2xl font-bold">{expenseStats.total}</p>
                  </div>
                  <div className="p-3 rounded-full bg-blue-500/10">
                    <Receipt className="w-6 h-6 text-blue-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 报销筛选 */}
          <div className="flex gap-2">
            {[
              { value: 'all', label: '全部' },
              { value: 'pending', label: '待审批' },
              { value: 'approved', label: '已通过' },
              { value: 'rejected', label: '已拒绝' },
            ].map((f) => (
              <Button
                key={f.value}
                variant={expenseFilter === f.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setExpenseFilter(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>

          {/* 报销记录 */}
          <Card>
            <CardHeader>
              <CardTitle>报销记录</CardTitle>
              <CardDescription>您的报销申请历史</CardDescription>
            </CardHeader>
            <CardContent>
              {expenseLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (() => {
                const filtered = expenseFilter === 'all'
                  ? expenseRecords
                  : expenseRecords.filter((a) => a.status === expenseFilter);
                return filtered.length === 0 ? (
                <div className="text-center py-12">
                  <Wallet className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">暂无报销记录</p>
                  <Button
                    variant="outline"
                    className="mt-4"
                    onClick={() => setExpenseDialogOpen(true)}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    提交第一笔报销
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {filtered.map((record) => (
                    <div
                      key={record.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className="text-sm">
                          <p className="font-medium truncate">{record.description || '无描述'}</p>
                          <p className="text-xs text-muted-foreground">
                            {getExpenseTypeLabel(record.type)} &middot;{' '}
                            {new Date(record.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 shrink-0">
                        <span className="font-medium">
                          {record.amount != null ? `¥${record.amount.toLocaleString()}` : '-'}
                        </span>
                        {getStatusBadge(record.status)}
                      </div>
                    </div>
                  ))}
                </div>
              );
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 发票管理 */}
        <TabsContent value="invoice" className="space-y-4">
          <div className="flex justify-end">
            <Button onClick={() => setInvoiceDialogOpen(true)} className="gap-2">
              <Plus className="w-4 h-4" />
              新建发票
            </Button>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>发票列表</CardTitle>
              <CardDescription>组织内的发票记录</CardDescription>
            </CardHeader>
            <CardContent>
              {invoiceLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : invoices.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">暂无发票记录</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {invoices.map((inv) => (
                    <div
                      key={inv.id}
                      className="flex items-center justify-between p-3 rounded-lg border"
                    >
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className="text-sm">
                          <p className="font-medium">{inv.invoice_number}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(inv.created_at).toLocaleDateString()}
                            {inv.due_date && ` | 到期: ${new Date(inv.due_date).toLocaleDateString()}`}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 shrink-0">
                        <span className="font-medium">¥{inv.amount.toLocaleString()}</span>
                        {getStatusBadge(inv.status)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 预算概览 */}
        <TabsContent value="budget" className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" className="gap-2" onClick={() => setBudgetDialogOpen(true)}>
              <Plus className="w-4 h-4" />
              新建预算
            </Button>
          </div>
          {budgetLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : budgets.length === 0 ? (
            <div className="text-center py-12 bg-muted/10 rounded-xl border border-dashed">
              <PiggyBank className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium">暂无预算数据</h3>
              <p className="text-muted-foreground mt-1">预算信息将由管理员配置后显示</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {budgets.map((budget) => {
                const usedPercent =
                  budget.total_amount > 0
                    ? Math.round((budget.used_amount / budget.total_amount) * 100)
                    : 0;
                const remaining = budget.total_amount - budget.used_amount;
                return (
                  <Card key={budget.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-base">{budget.name}</CardTitle>
                          <CardDescription>{budget.period}</CardDescription>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-primary"
                            onClick={() => handleEditBudget(budget)}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-red-500"
                            onClick={() => handleDeleteBudget(budget.id)}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">总预算</span>
                          <span className="font-medium">¥{budget.total_amount.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">已使用</span>
                          <span className="font-medium text-orange-500">
                            ¥{budget.used_amount.toLocaleString()}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">剩余</span>
                          <span
                            className={`font-medium ${remaining < 0 ? 'text-red-500' : 'text-green-500'}`}
                          >
                            ¥{remaining.toLocaleString()}
                          </span>
                        </div>
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>使用率</span>
                            <span>{usedPercent}%</span>
                          </div>
                          <Progress
                            value={Math.min(usedPercent, 100)}
                            className={`h-2 ${usedPercent > 90 ? '[&>div]:bg-red-500' : usedPercent > 70 ? '[&>div]:bg-yellow-500' : ''}`}
                          />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* 新建报销 Dialog */}
      <Dialog open={expenseDialogOpen} onOpenChange={setExpenseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建报销申请</DialogTitle>
            <DialogDescription>填写报销信息，提交后进入审批流程</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>报销类型</Label>
              <Select
                value={expenseForm.type}
                onValueChange={(v) => setExpenseForm({ ...expenseForm, type: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="expense">日常报销</SelectItem>
                  <SelectItem value="travel">差旅报销</SelectItem>
                  <SelectItem value="purchase">采购申请</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>金额 (元)</Label>
              <Input
                type="number"
                placeholder="0.00"
                value={expenseForm.amount || ''}
                onChange={(e) =>
                  setExpenseForm({ ...expenseForm, amount: Number(e.target.value) })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>报销说明</Label>
              <Textarea
                placeholder="请描述报销事由..."
                value={expenseForm.description}
                onChange={(e) =>
                  setExpenseForm({ ...expenseForm, description: e.target.value })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExpenseDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSubmitExpense} disabled={submitting}>
              {submitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              提交报销
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 新建预算 Dialog */}
      <Dialog open={budgetDialogOpen} onOpenChange={(open) => {
        setBudgetDialogOpen(open);
        if (!open) setEditingBudgetId(null);
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingBudgetId ? '编辑预算' : '新建预算'}</DialogTitle>
            <DialogDescription>设置部门或项目预算额度</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>预算名称</Label>
              <Input
                placeholder="例如：市场部Q1预算"
                value={budgetForm.name}
                onChange={(e) => setBudgetForm({ ...budgetForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>总金额 (元)</Label>
              <Input
                type="number"
                placeholder="0.00"
                value={budgetForm.total_amount || ''}
                onChange={(e) => setBudgetForm({ ...budgetForm, total_amount: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label>预算期间</Label>
              <Input
                type="month"
                value={budgetForm.period}
                onChange={(e) => setBudgetForm({ ...budgetForm, period: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBudgetDialogOpen(false)}>取消</Button>
            <Button onClick={handleSubmitBudget} disabled={budgetSubmitting}>
              {budgetSubmitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              {editingBudgetId ? '更新预算' : '创建预算'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 新建发票 Dialog */}
      <Dialog open={invoiceDialogOpen} onOpenChange={setInvoiceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建发票</DialogTitle>
            <DialogDescription>创建发票记录</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>发票号</Label>
              <Input
                placeholder="例如：INV-2026-001"
                value={invoiceForm.invoice_number}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, invoice_number: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>金额 (元)</Label>
              <Input
                type="number"
                placeholder="0.00"
                value={invoiceForm.amount || ''}
                onChange={(e) => setInvoiceForm({ ...invoiceForm, amount: Number(e.target.value) })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>到期日</Label>
                <Input
                  type="date"
                  value={invoiceForm.due_date}
                  onChange={(e) => setInvoiceForm({ ...invoiceForm, due_date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>状态</Label>
                <Select
                  value={invoiceForm.status}
                  onValueChange={(v) => setInvoiceForm({ ...invoiceForm, status: v })}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">草稿</SelectItem>
                    <SelectItem value="pending">待付款</SelectItem>
                    <SelectItem value="paid">已付款</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvoiceDialogOpen(false)}>取消</Button>
            <Button onClick={handleSubmitInvoice} disabled={invoiceSubmitting}>
              {invoiceSubmitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              创建发票
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default FinanceCenter;
