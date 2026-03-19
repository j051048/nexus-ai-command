import React, { useMemo, useState } from 'react';
import {
  CheckCircle2,
  BarChart3,
  Database,
  Loader2,
  History,
  Sparkles,
  Activity,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTeamPerformance, useLeaderboard, useSeedDemoData, useSalesMetricsRealtime } from '@/hooks/useSalesData';
import { useApprovals } from '@/hooks/useApprovals';
import { SalesHistoryPanel } from '@/components/sales';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { lazyWithRetry } from '@/lib/lazyPreload';
import { AlertWidget } from './AlertWidget';
import { AIActivityStats } from './AIActivityStats';

// Lazy load heavy components
const TeamPerformanceChart = lazyWithRetry(() => import('@/components/charts').then(m => ({ default: m.TeamPerformanceChart })));
const RevenueChart = lazyWithRetry(() => import('@/components/charts').then(m => ({ default: m.RevenueChart })));
const AIWeeklyReport = lazyWithRetry(() => import('./boss').then(m => ({ default: m.AIWeeklyReport })));
const ExceptionQueue = lazyWithRetry(() => import('./boss').then(m => ({ default: m.ExceptionQueue })));
const TeamPerformanceHeatmap = lazyWithRetry(() => import('./boss').then(m => ({ default: m.TeamPerformanceHeatmap })));
const TopPerformers = lazyWithRetry(() => import('./boss').then(m => ({ default: m.TopPerformers })));

const ChartSkeleton = () => (
  <div className="bg-card rounded-2xl p-6 border border-border h-[350px]">
    <Skeleton className="h-6 w-32 mb-4" />
    <Skeleton className="h-full w-full" />
  </div>
);

const SectionSkeleton = ({ className }: { className?: string }) => (
  <div className={cn("bg-card rounded-2xl p-6 border border-border", className)}>
    <Skeleton className="h-6 w-32 mb-4" />
    <Skeleton className="h-24 w-full" />
  </div>
);

const defaultWeeklyReport = {
  cashFlow: 0,
  cashFlowTrend: 0,
  salesRisks: [] as string[],
  totalIncentives: 0,
  topPerformers: [] as { name: string; score: number; bonus: number }[],
};

const teamHeatmap: { name: string; mon: number; tue: number; wed: number; thu: number; fri: number }[] = [];

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
    <div className="space-y-6 sm:space-y-8 animate-fade-in">
      {/* Hero Header with Glassmorphism */}
      <div className="relative overflow-hidden rounded-3xl glass cyber-border p-6 sm:p-8 hover-lift">
        {/* Animated background elements */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 rounded-full bg-primary/20 blur-3xl animate-pulse-glow" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 rounded-full bg-success/20 blur-3xl float" style={{ animationDelay: '1s' }} />
        
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-gradient-primary inline-flex animate-bounce-subtle">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-foreground to-foreground/60 tracking-tight">
                Nexus 智能中枢
              </h1>
            </div>
            <p className="text-base sm:text-lg text-muted-foreground flex items-center gap-2 mt-2 font-medium">
              <span className="flex h-2.5 w-2.5 rounded-full bg-success pulse-live" />
              AI 处理器已在线 · 今日共有 <span className="text-warning font-bold mx-1">{pendingApprovals.length}</span> 项决策需要您复核
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {!hasRealData && (
              <Button
                variant="outline"
                size="lg"
                onClick={handleSeedData}
                disabled={seedDemoData.isPending}
                className="flex items-center gap-2 bg-background/50 backdrop-blur-md border-primary/20 hover:bg-primary/10 transition-all rounded-xl shadow-lg"
              >
                {seedDemoData.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Database className="w-5 h-5 text-primary" />
                )}
                <span className="font-semibold">初始化业务数据流</span>
              </Button>
            )}
            <div className="flex items-center gap-3 px-5 py-3 glass bg-success/10 rounded-xl cyber-border animate-fade-slide-left shadow-lg">
               <div className="p-1.5 rounded-full bg-success/20 animate-pulse">
                  <Activity className="w-5 h-5 text-success" />
               </div>
               <div className="flex flex-col">
                 <span className="text-xs text-muted-foreground font-mono uppercase tracking-wider">Automated</span>
                 <span className="text-success font-bold text-sm sm:text-base">95% 事务已托管</span>
               </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation with Modern Pills */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 md:w-auto md:inline-flex p-1.5 glass rounded-2xl">
          <TabsTrigger value="overview" className="flex items-center gap-2 rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all duration-300">
            <BarChart3 className="w-4 h-4" />
            <span className="font-medium tracking-wide">全局监控</span>
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2 rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all duration-300">
            <History className="w-4 h-4" />
            <span className="font-medium tracking-wide">智能溯源</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 sm:space-y-8 mt-6">
          {/* 跨域数据预警 */}
          <AlertWidget />

          {/* AI 活跃度统计 */}
          <AIActivityStats />

          <div className="animate-fade-slide-up" style={{ animationDelay: '100ms', opacity: 0, animationFillMode: 'forwards' }}>
             <React.Suspense fallback={<SectionSkeleton />}>
               <AIWeeklyReport report={weeklyReport} />
             </React.Suspense>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
            <div className="animate-fade-slide-up hover-lift" style={{ animationDelay: '200ms', opacity: 0, animationFillMode: 'forwards' }}>
              <React.Suspense fallback={<ChartSkeleton />}>
                <div className="glass rounded-3xl p-1 h-full shadow-lg border border-border/40">
                  <RevenueChart />
                </div>
              </React.Suspense>
            </div>
            <div className="animate-fade-slide-up hover-lift" style={{ animationDelay: '300ms', opacity: 0, animationFillMode: 'forwards' }}>
              <React.Suspense fallback={<ChartSkeleton />}>
                <div className="glass rounded-3xl p-1 h-full shadow-lg border border-border/40">
                  <TeamPerformanceChart />
                </div>
              </React.Suspense>
            </div>
          </div>

          <div className="animate-fade-slide-up" style={{ animationDelay: '400ms', opacity: 0, animationFillMode: 'forwards' }}>
            <React.Suspense fallback={<SectionSkeleton />}>
              <div className="glass rounded-3xl overflow-hidden shadow-2xl border border-primary/20">
                <ExceptionQueue
                  pendingApprovals={pendingApprovals}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  isProcessing={updateStatus.isPending}
                />
              </div>
            </React.Suspense>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
            <div className="animate-fade-slide-up hover-lift" style={{ animationDelay: '500ms', opacity: 0, animationFillMode: 'forwards' }}>
              <React.Suspense fallback={<SectionSkeleton />}>
                <div className="glass rounded-3xl p-1 h-full shadow-lg border border-border/40">
                   <TeamPerformanceHeatmap data={teamHeatmap} />
                </div>
              </React.Suspense>
            </div>
            <div className="animate-fade-slide-up hover-lift" style={{ animationDelay: '600ms', opacity: 0, animationFillMode: 'forwards' }}>
              <React.Suspense fallback={<SectionSkeleton />}>
                 <div className="glass rounded-3xl p-1 h-full shadow-lg border border-border/40">
                   <TopPerformers performers={weeklyReport.topPerformers} />
                 </div>
              </React.Suspense>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="history" className="mt-6 animate-fade-in glass rounded-3xl p-2 border border-border/40 shadow-xl">
          <SalesHistoryPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
