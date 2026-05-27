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

  return (
    <AIInsightPanel
      title="AI 审批风控建议"
      icon={pending > 0 ? AlertTriangle : ShieldCheck}
      trustLevel={pending >= 10 ? 'low' : pending >= 3 ? 'medium' : 'high'}
      score={pending >= 10 ? 62 : pending >= 3 ? 78 : 92}
      summary={
        isBoss
          ? `当前有 ${pending} 条待处理审批。AI 会优先提示大额、说明不足、长时间停滞的申请，建议先处理异常项。`
          : `你发起的审批中有 ${mine} 条需要关注。AI 会提醒补充材料、跟踪进度和催办节点。`
      }
      context={['审批中心', isBoss ? '管理视角' : '个人视角', `风险 ${riskLevel}`]}
      evidence={[
        { label: '待处理', value: <span className="text-lg font-semibold">{pending}</span> },
        { label: '我发起的', value: <span className="text-lg font-semibold">{mine}</span> },
      ]}
      risks={pending >= 10 ? ['待处理审批积压', '建议先处理大额和停滞申请'] : pending >= 3 ? ['存在待复核审批'] : []}
      actions={[
        {
          label: '分析风险',
          variant: 'default',
          prompt: '请分析当前审批中心的风险项，按金额、说明完整度和停滞时间给出处理顺序。',
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
