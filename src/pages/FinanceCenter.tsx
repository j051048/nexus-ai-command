/**
 * 财务中心
 * 整合报销、预算等财务功能
 */

import React, { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import {
  DollarSign,
  Receipt,
  PieChart,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  XCircle,
  Clock3,
  Upload,
  Send,
  MessageSquare,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import { useUser } from '@/contexts/UserContext';
import { toast } from 'sonner';

// 报销类型配置
const expenseTypes = [
  { value: 'travel', label: '差旅费', icon: '✈️' },
  { value: 'entertainment', label: '招待费', icon: '🍽️' },
  { value: 'office', label: '办公用品', icon: '📎' },
  { value: 'transportation', label: '交通费', icon: '🚕' },
  { value: 'communication', label: '通讯费', icon: '📱' },
  { value: 'other', label: '其他', icon: '📋' },
];

// 模拟报销记录
const mockExpenses = [
  { id: '1', type: 'entertainment', amount: 786, description: '客户拜访餐费', date: '2024-12-18', status: 'approved', project: '华为云项目' },
  { id: '2', type: 'travel', amount: 3200, description: '上海出差', date: '2024-12-15', status: 'paid', project: '' },
  { id: '3', type: 'transportation', amount: 156, description: '打车费', date: '2024-12-19', status: 'pending', project: '' },
  { id: '4', type: 'office', amount: 299, description: '购买文具', date: '2024-12-10', status: 'rejected', project: '', reason: '缺少发票' },
];

// 模拟预算数据
const mockBudgets = [
  { category: '差旅费', planned: 50000, used: 32500, percentage: 65 },
  { category: '招待费', planned: 30000, used: 18000, percentage: 60 },
  { category: '办公费', planned: 20000, used: 15500, percentage: 77.5 },
  { category: '培训费', planned: 15000, used: 8000, percentage: 53.3 },
  { category: '营销费', planned: 80000, used: 72000, percentage: 90 },
];

export function FinanceCenter() {
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState('expense');
  const [expenseType, setExpenseType] = useState('');
  const [amount, setAmount] = useState('');

  const handleQuickExpense = () => {
    toast.success('已跳转到AI助手，请用自然语言描述您的报销需求');
  };

  const handleSubmitExpense = () => {
    if (!expenseType || !amount) {
      toast.error('请填写完整信息');
      return;
    }
    toast.success('报销申请已提交');
  };

  const statusConfig = {
    pending: { label: '审批中', icon: <Clock3 className="w-4 h-4" />, color: 'text-yellow-500 bg-yellow-500/10' },
    approved: { label: '已批准', icon: <CheckCircle2 className="w-4 h-4" />, color: 'text-blue-500 bg-blue-500/10' },
    paid: { label: '已到账', icon: <CheckCircle2 className="w-4 h-4" />, color: 'text-green-500 bg-green-500/10' },
    rejected: { label: '已拒绝', icon: <XCircle className="w-4 h-4" />, color: 'text-red-500 bg-red-500/10' },
  };

  // 计算统计数据
  const totalPending = mockExpenses.filter(e => e.status === 'pending').reduce((sum, e) => sum + e.amount, 0);
  const totalApproved = mockExpenses.filter(e => e.status === 'approved').reduce((sum, e) => sum + e.amount, 0);
  const totalPaid = mockExpenses.filter(e => e.status === 'paid').reduce((sum, e) => sum + e.amount, 0);
  const totalThisMonth = mockExpenses.reduce((sum, e) => sum + e.amount, 0);

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">财务中心</h1>
          <p className="text-muted-foreground">管理报销申请和查看预算</p>
        </div>
        <Button onClick={handleQuickExpense} className="gap-2">
          <MessageSquare className="w-4 h-4" />
          用AI助手报销
        </Button>
      </div>

      {/* 快捷统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">待审批</p>
                <p className="text-2xl font-bold text-yellow-500">¥{totalPending.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-full bg-yellow-500/10">
                <Clock3 className="w-6 h-6 text-yellow-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">待付款</p>
                <p className="text-2xl font-bold text-blue-500">¥{totalApproved.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-full bg-blue-500/10">
                <FileText className="w-6 h-6 text-blue-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">已到账</p>
                <p className="text-2xl font-bold text-green-500">¥{totalPaid.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-full bg-green-500/10">
                <CheckCircle2 className="w-6 h-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">本月报销</p>
                <p className="text-2xl font-bold">¥{totalThisMonth.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-full bg-purple-500/10">
                <Receipt className="w-6 h-6 text-purple-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 主内容区 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="expense" className="gap-2">
            <Receipt className="w-4 h-4" />
            报销管理
          </TabsTrigger>
          <TabsTrigger value="budget" className="gap-2">
            <PieChart className="w-4 h-4" />
            预算概览
          </TabsTrigger>
        </TabsList>

        {/* 报销管理 */}
        <TabsContent value="expense" className="space-y-4">
          <div className="grid md:grid-cols-2 gap-6">
            {/* 报销申请表单 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">发起报销</CardTitle>
                <CardDescription>填写报销信息或使用AI助手快速申请</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>费用类型</Label>
                  <Select value={expenseType} onValueChange={setExpenseType}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择费用类型" />
                    </SelectTrigger>
                    <SelectContent>
                      {expenseTypes.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.icon} {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>金额 (元)</Label>
                  <Input
                    type="number"
                    placeholder="请输入报销金额"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label>费用说明</Label>
                  <Textarea placeholder="请描述费用用途..." />
                </div>

                <div className="space-y-2">
                  <Label>上传发票</Label>
                  <div className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:bg-muted/50 transition">
                    <Upload className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">点击或拖拽上传发票图片</p>
                    <p className="text-xs text-muted-foreground mt-1">支持 JPG, PNG, PDF 格式</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button className="flex-1 gap-2" onClick={handleSubmitExpense}>
                    <Send className="w-4 h-4" />
                    提交报销
                  </Button>
                  <Button variant="outline" onClick={handleQuickExpense} className="gap-2">
                    <MessageSquare className="w-4 h-4" />
                    AI助手
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* 报销记录 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">报销记录</CardTitle>
                <CardDescription>最近的报销申请</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {mockExpenses.map((expense) => {
                    const status = statusConfig[expense.status as keyof typeof statusConfig];
                    const expType = expenseTypes.find(t => t.value === expense.type);
                    return (
                      <div key={expense.id} className="p-3 rounded-lg border space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">{expType?.icon}</span>
                            <div>
                              <p className="font-medium">¥{expense.amount.toLocaleString()}</p>
                              <p className="text-sm text-muted-foreground">{expense.description}</p>
                            </div>
                          </div>
                          <Badge className={cn('gap-1', status.color)}>
                            {status.icon}
                            {status.label}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{expense.date}</span>
                          {expense.project && <span>关联: {expense.project}</span>}
                        </div>
                        {expense.status === 'rejected' && expense.reason && (
                          <div className="text-xs text-red-500 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            拒绝原因: {expense.reason}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 预算概览 */}
        <TabsContent value="budget" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>部门预算使用情况</CardTitle>
              <CardDescription>2024年12月 · {user.department || '销售部'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {mockBudgets.map((budget) => (
                <div key={budget.category} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{budget.category}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">
                        ¥{budget.used.toLocaleString()} / ¥{budget.planned.toLocaleString()}
                      </span>
                      {budget.percentage > 80 && (
                        <Badge variant="destructive" className="text-xs">
                          <AlertTriangle className="w-3 h-3 mr-1" />
                          预警
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="relative">
                    <Progress 
                      value={budget.percentage} 
                      className={cn(
                        "h-3",
                        budget.percentage > 80 && "[&>div]:bg-red-500"
                      )}
                    />
                    <span className="absolute right-0 top-0 text-xs text-muted-foreground transform translate-y-4">
                      {budget.percentage}%
                    </span>
                  </div>
                </div>
              ))}

              {/* 汇总 */}
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <span className="font-medium">总预算</span>
                  <div className="text-right">
                    <p className="font-bold">
                      ¥{mockBudgets.reduce((s, b) => s + b.used, 0).toLocaleString()} / 
                      ¥{mockBudgets.reduce((s, b) => s + b.planned, 0).toLocaleString()}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      剩余 ¥{(mockBudgets.reduce((s, b) => s + b.planned, 0) - mockBudgets.reduce((s, b) => s + b.used, 0)).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default FinanceCenter;