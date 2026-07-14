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
import { AIInsightPanel } from '@/components/ai/AIInsightPanel';
import { AlertTriangle, Plus, ShieldCheck } from 'lucide-react';

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
      surfaceId="approval-risk"
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
  const [showCreate, setShowCreate] = useState(false);

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
    setShowCreate(true);
    // 切换到"我发起的"标签页，方便提交后查看
    if (activeTab === 'pending') {
      setActiveTab('mine');
    }
  };

  return (
    <div
      ref={containerRef}
      {...handlers}
      className="mx-auto max-w-[1400px] space-y-4 pb-20"
    >
      {/* Pull to Refresh Indicator (mobile only) */}
      {isMobile && (
        <PullToRefreshIndicator pullDistance={pullDistance} isRefreshing={isRefreshing} />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-foreground">审批中心</h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            {isBoss ? (
              <>处理待审核事项并复核异常申请</>
            ) : (
              <>发起申请并查看处理进度</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowCreate((value) => !value)}>
            <Plus className="mr-1.5 h-4 w-4" />
            发起审批
          </Button>
          <NotificationBell />
        </div>
      </div>

      <ApprovalAIRiskPanel
        isBoss={isBoss}
        pending={tabCounts?.pending ?? 0}
        mine={tabCounts?.mine ?? 0}
      />

      {/* 审批类型入口卡片（动态渲染） */}
      {showCreate && typeConfigs.length > 0 && (
        <section className="border-y bg-card/45 px-3 py-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">选择审批类型</h2>
            <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>收起</Button>
          </div>
          <ApprovalTypeGrid
            types={typeConfigs}
            selectedType={selectedTypeCode}
            onSelect={handleTypeSelect}
          />
        </section>
      )}

      {/* 选中类型后展开提交表单（复用 EmployeeApprovalView） */}
      {showCreate && selectedTypeCode && (
        <div className="border-y bg-card/45 p-1">
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
