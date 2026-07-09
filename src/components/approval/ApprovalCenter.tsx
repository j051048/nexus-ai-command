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
import { AIInsightPanel } from '@/components/ai/AIInsightPanel';
import { AlertTriangle, ShieldCheck } from 'lucide-react';

function ApprovalAIRiskPanel({
  isBoss,
  pending,
  mine,
}: {
  isBoss: boolean;
  pending: number;
  mine: number;
}) {
  const riskLevel = pending >= 10 ? '低' : pending >= 3 ? '需复核' : '高';
  const trustLevel = pending >= 10 ? 'low' : pending >= 3 ? 'medium' : 'high';
  const score = pending >= 10 ? 62 : pending >= 3 ? 78 : 92;
  const summary = isBoss
    ? pending > 0
      ? `${pending} 条待处理，优先看大额、说明不足或停滞申请。`
      : '当前没有积压审批，可以让 AI 生成审批规则建议。'
    : mine > 0
      ? `${mine} 条我发起的审批需要关注进度或补材料。`
      : '暂无需要跟进的审批。';

  return (
    <AIInsightPanel
      variant="compact"
      icon={pending > 0 ? AlertTriangle : ShieldCheck}
      title="下一步审批动作"
      summary={summary}
      trustLevel={trustLevel}
      score={score}
      stats={[
        { label: '待处理', value: pending },
        { label: '我发起', value: mine },
        { label: '风险', value: riskLevel },
      ]}
      actions={[
        {
          label: '分析风险',
          prompt: '请分析当前审批中心的风险项，按金额、说明完整度和停滞时间给出处理顺序。',
          variant: 'default',
        },
      ]}
    />
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
