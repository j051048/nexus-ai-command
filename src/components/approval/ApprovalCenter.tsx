import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Send,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Plane,
  ShoppingCart,
  Receipt,
  Calendar,
  Bot,
  Sparkles,
  XCircle,
  Loader2,
  Bell,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { useAuth } from '@/components/auth/AuthContext';
import {
  useMyApprovals,
  useAllApprovals,
  useSubmitApproval,
  useApproveRequest,
  useRejectRequest,
  useNotifications,
  useApprovalsRealtime,
  useNotificationsRealtime,
  usePendingApprovalsCount,
  ApprovalRequest,
} from '@/hooks/useApprovals';

const approvalTypes = [
  { id: 'travel' as const, name: '出差申请', icon: <Plane className="w-5 h-5" />, example: '下周去上海出差见客户，预算2500，包括高铁和酒店', threshold: 3000 },
  { id: 'purchase' as const, name: '采购申请', icon: <ShoppingCart className="w-5 h-5" />, example: '采购一台示波器，型号DSO1104，预算8000元', threshold: 5000 },
  { id: 'expense' as const, name: '费用报销', icon: <Receipt className="w-5 h-5" />, example: '报销上周客户拜访餐费320元，附发票', threshold: 500 },
  { id: 'leave' as const, name: '请假申请', icon: <Calendar className="w-5 h-5" />, example: '申请下周一年假一天，处理私事', threshold: 3 },
];

const statusConfig = {
  pending: { label: '处理中', color: 'bg-primary/20 text-primary', icon: <Clock className="w-4 h-4" /> },
  auto_approved: { label: '已自动通过', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-4 h-4" /> },
  requires_boss: { label: '待老板审批', color: 'bg-warning/20 text-warning', icon: <Clock className="w-4 h-4" /> },
  approved: { label: '已批准', color: 'bg-success/20 text-success', icon: <CheckCircle2 className="w-4 h-4" /> },
  rejected: { label: '已驳回', color: 'bg-destructive/20 text-destructive', icon: <XCircle className="w-4 h-4" /> },
};

export function ApprovalCenter() {
  const { role } = useAuth();
  const isBoss = role === 'boss';

  // Enable realtime subscriptions
  useApprovalsRealtime();
  useNotificationsRealtime();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">智能审批中心</h1>
          <p className="text-muted-foreground mt-1">
            {isBoss ? 'AI自动处理常规审批，仅异常需您决策' : '一句话提交，AI秒速处理'}
          </p>
        </div>
        <NotificationBell />
      </div>

      {isBoss ? <BossApprovalView /> : <EmployeeApprovalView />}
    </div>
  );
}

// Notification Bell Component
function NotificationBell() {
  const [showNotifications, setShowNotifications] = useState(false);
  const { data: notifications } = useNotifications();
  
  const unreadCount = notifications?.filter(n => !n.read).length || 0;

  return (
    <>
      <Button
        variant="outline"
        size="icon"
        className="relative"
        onClick={() => setShowNotifications(true)}
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-white text-xs rounded-full flex items-center justify-center">
            {unreadCount}
          </span>
        )}
      </Button>

      <Dialog open={showNotifications} onOpenChange={setShowNotifications}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>通知</DialogTitle>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto space-y-2">
            {!notifications || notifications.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">暂无通知</p>
            ) : (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={cn(
                    "p-3 rounded-lg border",
                    notification.read ? "bg-secondary/30" : "bg-primary/5 border-primary/20"
                  )}
                >
                  <p className="font-medium text-foreground text-sm">{notification.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{notification.message}</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    {new Date(notification.created_at).toLocaleString('zh-CN')}
                  </p>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Employee View
function EmployeeApprovalView() {
  const [input, setInput] = useState('');
  const [amount, setAmount] = useState<number>(0);
  const [selectedType, setSelectedType] = useState<typeof approvalTypes[0] | null>(null);

  const { data: myApprovals, isLoading } = useMyApprovals();
  const submitApproval = useSubmitApproval();

  const handleSubmit = async () => {
    if (!input.trim() || !selectedType) {
      toast.error('请选择申请类型并填写说明');
      return;
    }

    try {
      const result = await submitApproval.mutateAsync({
        type: selectedType.id,
        description: input,
        amount,
      });

      if (result.auto_approved) {
        toast.success('已自动审批通过！');
      } else {
        toast.success('已提交，等待老板审批');
      }

      setInput('');
      setAmount(0);
      setSelectedType(null);
    } catch (error: any) {
      toast.error('提交失败: ' + error.message);
    }
  };

  const useExample = (type: typeof approvalTypes[0]) => {
    setSelectedType(type);
    setInput(type.example);
    // Extract amount from example if possible
    const amountMatch = type.example.match(/(\d+)/);
    if (amountMatch) {
      setAmount(parseInt(amountMatch[1]));
    }
  };

  // Calculate stats
  const stats = {
    total: myApprovals?.length || 0,
    autoApproved: myApprovals?.filter(a => a.status === 'auto_approved').length || 0,
    pending: myApprovals?.filter(a => a.status === 'requires_boss').length || 0,
  };

  return (
    <>
      {/* Quick Submit */}
      <div className="bg-gradient-card rounded-2xl p-6 cyber-border">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">AI审批管家</h2>
            <p className="text-xs text-muted-foreground">用自然语言描述您的需求，AI自动识别并处理</p>
          </div>
        </div>

        {/* Type Shortcuts */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {approvalTypes.map((type) => (
            <button
              key={type.id}
              onClick={() => useExample(type)}
              className={cn(
                "p-4 rounded-xl border transition-all text-left",
                selectedType?.id === type.id
                  ? "border-primary bg-primary/10"
                  : "border-border bg-secondary/50 hover:border-primary/50"
              )}
            >
              <div className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center mb-3",
                selectedType?.id === type.id ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              )}>
                {type.icon}
              </div>
              <p className="font-medium text-foreground text-sm">{type.name}</p>
              <p className="text-xs text-muted-foreground mt-1">
                自动通过: ≤¥{type.threshold}
              </p>
            </button>
          ))}
        </div>

        {/* Amount Input */}
        <div className="mb-4">
          <label className="text-sm text-muted-foreground mb-2 block">金额 (¥)</label>
          <Input
            type="number"
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            placeholder="请输入金额"
            className="max-w-xs"
          />
        </div>

        {/* Input Area */}
        <div className="relative">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="描述您的申请，例如：下周二出差去上海拜访客户，预算3000元..."
            className="min-h-32 resize-none pr-28"
          />
          <Button
            onClick={handleSubmit}
            disabled={!input.trim() || !selectedType || submitApproval.isPending}
            className="absolute bottom-4 right-4"
          >
            {submitApproval.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                处理中...
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                提交申请
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">本月审批</p>
              <p className="text-2xl font-bold text-foreground mt-1">{stats.total}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6 text-primary" />
            </div>
          </div>
        </div>
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">自动通过</p>
              <p className="text-2xl font-bold text-success mt-1">{stats.autoApproved}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-success/20 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-success" />
            </div>
          </div>
        </div>
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">待审批</p>
              <p className="text-2xl font-bold text-warning mt-1">{stats.pending}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-warning/20 flex items-center justify-center">
              <Clock className="w-6 h-6 text-warning" />
            </div>
          </div>
        </div>
      </div>

      {/* History */}
      <ApprovalHistory approvals={myApprovals} isLoading={isLoading} />
    </>
  );
}

// Boss View
function BossApprovalView() {
  const [statusFilter, setStatusFilter] = useState('requires_boss');
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const { data: allApprovals, isLoading } = useAllApprovals(statusFilter);
  const { data: pendingCount } = usePendingApprovalsCount();
  const approveRequest = useApproveRequest();
  const rejectRequest = useRejectRequest();

  const handleApprove = async (requestId: string) => {
    try {
      await approveRequest.mutateAsync(requestId);
      toast.success('已批准');
    } catch (error: any) {
      toast.error('操作失败: ' + error.message);
    }
  };

  const handleReject = async () => {
    if (!rejectingId || !rejectReason.trim()) {
      toast.error('请填写驳回原因');
      return;
    }

    try {
      await rejectRequest.mutateAsync({ requestId: rejectingId, reason: rejectReason });
      toast.success('已驳回');
      setRejectingId(null);
      setRejectReason('');
    } catch (error: any) {
      toast.error('操作失败: ' + error.message);
    }
  };

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">待审批</p>
              <p className="text-2xl font-bold text-warning mt-1">{pendingCount || 0}</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-warning/20 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-warning" />
            </div>
          </div>
        </div>
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">今日处理</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {allApprovals?.filter(a => 
                  new Date(a.submitted_at).toDateString() === new Date().toDateString()
                ).length || 0}
              </p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6 text-primary" />
            </div>
          </div>
        </div>
        <div className="bg-card rounded-xl p-5 border border-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">AI自动处理率</p>
              <p className="text-2xl font-bold text-success mt-1">95%</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-success/20 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-success" />
            </div>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <Tabs value={statusFilter} onValueChange={setStatusFilter}>
        <TabsList>
          <TabsTrigger value="requires_boss" className="relative">
            待审批
            {(pendingCount || 0) > 0 && (
              <span className="ml-2 px-1.5 py-0.5 text-xs bg-warning text-white rounded-full">
                {pendingCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="approved">已批准</TabsTrigger>
          <TabsTrigger value="rejected">已驳回</TabsTrigger>
          <TabsTrigger value="auto_approved">自动通过</TabsTrigger>
          <TabsTrigger value="all">全部</TabsTrigger>
        </TabsList>

        <TabsContent value={statusFilter} className="mt-4">
          <div className="bg-card rounded-2xl p-6 border border-border">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : !allApprovals || allApprovals.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <CheckCircle2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>暂无审批记录</p>
              </div>
            ) : (
              <div className="space-y-3">
                {allApprovals.map((approval) => (
                  <BossApprovalCard
                    key={approval.id}
                    approval={approval}
                    onApprove={() => handleApprove(approval.id)}
                    onReject={() => setRejectingId(approval.id)}
                    isApproving={approveRequest.isPending}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Reject Dialog */}
      <Dialog open={!!rejectingId} onOpenChange={() => setRejectingId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>驳回原因</DialogTitle>
          </DialogHeader>
          <Textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="请填写驳回原因..."
            className="min-h-24"
          />
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setRejectingId(null)}>取消</Button>
            <Button 
              variant="destructive" 
              onClick={handleReject}
              disabled={rejectRequest.isPending}
            >
              {rejectRequest.isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              确认驳回
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Boss Approval Card
function BossApprovalCard({
  approval,
  onApprove,
  onReject,
  isApproving,
}: {
  approval: ApprovalRequest;
  onApprove: () => void;
  onReject: () => void;
  isApproving: boolean;
}) {
  const status = statusConfig[approval.status as keyof typeof statusConfig];
  const typeInfo = approvalTypes.find(t => t.id === approval.type);
  const isPending = approval.status === 'requires_boss';

  return (
    <div className={cn(
      "p-4 rounded-xl border transition-colors",
      isPending ? "border-warning/50 bg-warning/5" : "border-border bg-secondary/50"
    )}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4 flex-1">
          <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
            {typeInfo?.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-medium text-foreground">{approval.description}</p>
              <span className={cn("flex items-center gap-1 px-2 py-0.5 rounded-full text-xs", status.color)}>
                {status.icon}
                {status.label}
              </span>
            </div>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground flex-wrap">
              <span>申请人：{approval.submitter_name}</span>
              <span className="font-medium text-foreground">¥{approval.amount}</span>
              <span>{new Date(approval.submitted_at).toLocaleString('zh-CN')}</span>
            </div>
            {approval.ai_reason && (
              <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                <Bot className="w-3 h-3" />
                AI: {approval.ai_reason}
              </p>
            )}
            {approval.rejection_reason && (
              <p className="text-xs text-destructive mt-2">
                驳回原因：{approval.rejection_reason}
              </p>
            )}
          </div>
        </div>

        {isPending && (
          <div className="flex gap-2 flex-shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={onReject}
              className="text-destructive hover:text-destructive"
            >
              <XCircle className="w-4 h-4 mr-1" />
              驳回
            </Button>
            <Button
              size="sm"
              onClick={onApprove}
              disabled={isApproving}
              className="bg-success hover:bg-success/90"
            >
              {isApproving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4 mr-1" />
              )}
              批准
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// Approval History Component
function ApprovalHistory({ 
  approvals, 
  isLoading 
}: { 
  approvals?: ApprovalRequest[]; 
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-2xl p-6 border border-border">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-foreground">审批记录</h2>
      </div>

      {!approvals || approvals.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>暂无审批记录</p>
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map((item) => {
            const status = statusConfig[item.status as keyof typeof statusConfig];
            const typeInfo = approvalTypes.find(t => t.id === item.type);
            
            return (
              <div
                key={item.id}
                className="flex items-center gap-4 p-4 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center text-muted-foreground">
                  {typeInfo?.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground truncate">{item.description}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(item.submitted_at).toLocaleString('zh-CN')}
                  </p>
                </div>
                {item.amount > 0 && (
                  <p className="text-sm font-medium text-foreground">¥{item.amount}</p>
                )}
                <div className={cn("flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium", status.color)}>
                  {status.icon}
                  {status.label}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
