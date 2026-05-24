import React, { useCallback, useState } from 'react';
import { useAuth } from '@/components/auth/AuthContext';
import { useApprovalsRealtime } from '@/hooks/useApprovals';
import { useNotificationsRealtime } from '@/hooks/useNotifications';
import { NotificationBell } from './sections/NotificationBell';
import { EmployeeApprovalView } from './sections/EmployeeApprovalView';
import { BossApprovalView } from './sections/BossApprovalView';
import { ApprovalTypeGrid } from './components/ApprovalTypeGrid';
import { useApprovalTypeConfig } from '@/hooks/useApprovalTypeConfig';
import { useTabCounts } from '@/hooks/useUnifiedApprovals';
import { useIsMobile } from '@/hooks/use-mobile';
import { usePullToRefresh } from '@/hooks/usePullToRefresh';
import { PullToRefreshIndicator } from '@/components/common/PullToRefreshIndicator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AIQuickActions } from '@/components/ai/AIQuickActions';
import { AlertTriangle, ShieldCheck, Sparkles } from 'lucide-react';

function triggerAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('proactive-chat', { detail: { message: prompt } }));
}

function ApprovalAIRiskPanel({
  isBoss,
  pending,
  mine,
}: {
  isBoss: boolean;
  pending: number;
  mine: number;
}) {
  const riskLevel = pending >= 10 ? '高' : pending >= 3 ? '中' : '低';

  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {pending > 0 ? <AlertTriangle className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold">AI 审批风控建议</h2>
              <Badge variant={pending >= 10 ? 'destructive' : 'secondary'}>风险 {riskLevel}</Badge>
            </div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              {isBoss
                ? `当前有 ${pending} 条待处理审批。AI 会优先提示大额、说明不足、长时间停滞的申请，建议先处理异常项。`
                : `你发起的审批中有 ${mine} 条需要关注。AI 会提醒补充材料、跟踪进度和催办节点。`}
            </p>
          </div>
        </div>
        <div className="grid gap-2 text-sm sm:grid-cols-3 lg:min-w-[360px]">
          <div className="rounded-lg border bg-background/70 p-3">
            <div className="text-xs text-muted-foreground">待处理</div>
            <div className="mt-1 text-lg font-semibold">{pending}</div>
          </div>
          <div className="rounded-lg border bg-background/70 p-3">
            <div className="text-xs text-muted-foreground">我发起的</div>
            <div className="mt-1 text-lg font-semibold">{mine}</div>
          </div>
          <Button
            className="h-full min-h-[64px]"
            variant="outline"
            onClick={() =>
              triggerAI('请分析当前审批中心的风险项，按金额、说明完整度和停滞时间给出处理顺序。')
            }
          >
            <Sparkles className="mr-2 h-4 w-4" />
            分析风险
          </Button>
        </div>
      </div>
    </section>
  );
}

export function ApprovalCenter() {
  const { role } = useAuth();
  const isBoss = role === 'boss' || role === 'founder';
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState(isBoss ? 'pending' : 'mine');

  // 数据源
  const { data: typeConfigs = [] } = useApprovalTypeConfig();
  const { data: tabCounts } = useTabCounts();

  // 选中的审批类型（用于展开提交表单）
  const [selectedTypeCode, setSelectedTypeCode] = useState<string | null>(null);

  // Enable realtime subscriptions for the entire section
  useApprovalsRealtime();
  useNotificationsRealtime();

  // 下拉刷新
  const handleRefresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['approvals'] });
    await queryClient.invalidateQueries({ queryKey: ['notifications'] });
    await queryClient.invalidateQueries({ queryKey: ['approval-tab-counts'] });
    await queryClient.invalidateQueries({ queryKey: ['approval-type-config'] });
    toast.success('审批数据已刷新');
  }, [queryClient]);

  const { isRefreshing, pullDistance, containerRef, handlers } = usePullToRefresh({
    onRefresh: handleRefresh,
    enabled: isMobile,
  });

  const handleTypeSelect = (typeCode: string) => {
    setSelectedTypeCode(prev => prev === typeCode ? null : typeCode);
    // 切换到"我发起的"标签页，方便提交后查看
    if (activeTab === 'pending') {
      setActiveTab('mine');
    }
  };

  return (
    <div
      ref={containerRef}
      {...handlers}
      className="max-w-[1400px] mx-auto space-y-6 pb-20 animate-in fade-in slide-in-from-bottom-2 duration-500"
    >
      {/* Pull to Refresh Indicator (mobile only) */}
      {isMobile && (
        <PullToRefreshIndicator pullDistance={pullDistance} isRefreshing={isRefreshing} />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight">审批中心</h1>
          <p className="text-muted-foreground mt-2 flex items-center gap-2">
            {isBoss ? (
              <>AI 引擎正在自动扫描常规申请，仅将异常推送至此处</>
            ) : (
              <>选择审批类型快速发起申请，AI 秒级分类并处理</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <NotificationBell />
        </div>
      </div>

      <AIQuickActions pageType="approval" />

      <ApprovalAIRiskPanel
        isBoss={isBoss}
        pending={tabCounts?.pending ?? 0}
        mine={tabCounts?.mine ?? 0}
      />

      {/* 审批类型入口卡片（动态渲染） */}
      {typeConfigs.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            发起审批
          </h2>
          <ApprovalTypeGrid
            types={typeConfigs}
            selectedType={selectedTypeCode}
            onSelect={handleTypeSelect}
          />
        </div>
      )}

      {/* 选中类型后展开提交表单（复用 EmployeeApprovalView） */}
      {selectedTypeCode && (
        <div className="border rounded-xl p-1">
          <EmployeeApprovalView />
        </div>
      )}

      {/* 三标签页 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 sm:w-auto sm:inline-grid">
          <TabsTrigger value="pending" className="gap-2">
            待处理
            {(tabCounts?.pending ?? 0) > 0 && (
              <Badge variant="destructive" className="ml-1 h-5 min-w-[20px] px-1.5 text-[10px]">
                {tabCounts!.pending}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="mine" className="gap-2">
            我发起的
            {(tabCounts?.mine ?? 0) > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 min-w-[20px] px-1.5 text-[10px]">
                {tabCounts!.mine}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="handled">已处理</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-4">
          <BossApprovalView />
        </TabsContent>

        <TabsContent value="mine" className="mt-4">
          <EmployeeApprovalView />
        </TabsContent>

        <TabsContent value="handled" className="mt-4">
          <BossApprovalView />
        </TabsContent>
      </Tabs>
    </div>
  );
}
