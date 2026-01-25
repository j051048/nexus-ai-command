import React, { useMemo, useState } from 'react';
import {
  CheckCircle2,
  BarChart3,
  Database,
  Loader2,
  History,
} from 'lucide-react';
import { TeamPerformanceChart, RevenueChart } from '@/components/charts';
import { useTeamPerformance, useLeaderboard, useSeedDemoData, useSalesMetricsRealtime } from '@/hooks/useSalesData';
import { useApprovals } from '@/hooks/useApprovals';
import { SalesHistoryPanel } from '@/components/sales';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AIWeeklyReport,
  ExceptionQueue,
  TeamPerformanceHeatmap,
  TopPerformers
} from './boss';

const defaultWeeklyReport = {
  cashFlow: 1250000,
  cashFlowTrend: 12.5,
  salesRisks: [
    '张教授商机超过30天未推进',
    '李博士报价已过期7天',
  ],
  totalIncentives: 28500,
  topPerformers: [
    { name: '王晓明', score: 95, bonus: 8200 },
    { name: '刘芳', score: 91, bonus: 6800 },
    { name: '张明', score: 87, bonus: 4850 },
  ],
};

const teamHeatmap = [
  { name: '王晓明', mon: 95, tue: 88, wed: 92, thu: 90, fri: 95 },
  { name: '刘芳', mon: 85, tue: 91, wed: 88, thu: 92, fri: 89 },
  { name: '张明', mon: 80, tue: 85, wed: 87, thu: 88, fri: 90 },
  { name: '陈伟', mon: 75, tue: 78, wed: 82, thu: 80, fri: 78 },
  { name: '李娜', mon: 70, tue: 75, wed: 78, thu: 76, fri: 80 },
];

export function BossDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  // 接入真实审批数据 Hook
  const { pendingApprovals, updateStatus } = useApprovals();

  const handleApprove = async (id: string) => {
    try {
      await updateStatus.mutateAsync({ id, status: 'approved' });
      toast.success('申请批准成功');
    } catch (e: unknown) {
      const err = e as Error;
      toast.error('操作失败: ' + (err?.message || '未知错误'));
    }
  };

  const handleReject = async (id: string) => {
    try {
      await updateStatus.mutateAsync({ id, status: 'rejected' });
      toast.success('申请已驳回');
    } catch (e: unknown) {
      const err = e as Error;
      toast.error('操作失败: ' + (err?.message || '未知错误'));
    }
  };

  // Enable realtime subscription for live updates
  useSalesMetricsRealtime();

  // Fetch real data
  const { data: teamData } = useTeamPerformance();
  const { data: leaderboardData } = useLeaderboard(3);
  const seedDemoData = useSeedDemoData();

  // Calculate weekly report from real data
  const weeklyReport = useMemo(() => {
    if (!leaderboardData || leaderboardData.length === 0) {
      return defaultWeeklyReport;
    }

    const totalBonus = leaderboardData.reduce((sum, p) => sum + p.bonus, 0);

    return {
      ...defaultWeeklyReport,
      totalIncentives: totalBonus,
      topPerformers: leaderboardData.map(p => ({
        name: p.name,
        score: p.score,
        bonus: p.bonus,
      })),
    };
  }, [leaderboardData]);

  const hasRealData = leaderboardData && leaderboardData.length > 0;

  const handleSeedData = async () => {
    try {
      await seedDemoData.mutateAsync();
      toast.success('已生成90天示例数据！');
    } catch (error: unknown) {
      const err = error as Error;
      toast.error('生成数据失败: ' + err.message);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-foreground">总控中心</h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">
            早上好！今日仅有 <span className="text-warning font-semibold">{pendingApprovals.length}</span> 条异常需要您处理
          </p>
        </div>
        <div className="flex items-center gap-3">
          {!hasRealData && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSeedData}
              disabled={seedDemoData.isPending}
              className="flex items-center gap-2"
            >
              {seedDemoData.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Database className="w-4 h-4" />
              )}
              生成示例数据
            </Button>
          )}
          <div className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-success/20 rounded-xl">
            <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-success" />
            <span className="text-success font-medium text-sm sm:text-base">95% 事务已由AI自动处理</span>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 sm:w-auto sm:inline-flex">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            概览
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <History className="w-4 h-4" />
            历史查询
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 sm:space-y-6 mt-4">
          <AIWeeklyReport report={weeklyReport} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            <RevenueChart />
            <TeamPerformanceChart />
          </div>

          <ExceptionQueue
            pendingApprovals={pendingApprovals}
            onApprove={handleApprove}
            onReject={handleReject}
            isProcessing={updateStatus.isPending}
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TeamPerformanceHeatmap data={teamHeatmap} />
            <TopPerformers performers={weeklyReport.topPerformers} />
          </div>
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <SalesHistoryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
