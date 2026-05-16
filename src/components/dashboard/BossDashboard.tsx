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
import { Navigate } from 'react-router-dom';

import { lazyWithRetry } from '@/lib/lazyPreload';
import { AlertWidget } from './AlertWidget';
import { AIActivityStats } from './AIActivityStats';
import { AIQuickActions } from '@/components/ai/AIQuickActions';
import { useAuth } from '@/components/auth/AuthContext';
import { LaunchChecklistPanel } from '@/components/product/LaunchChecklistPanel';

const TeamPerformanceChart = lazyWithRetry(() => import('@/components/charts').then(m => ({ default: m.TeamPerformanceChart })));
const RevenueChart = lazyWithRetry(() => import('@/components/charts').then(m => ({ default: m.RevenueChart })));
const AIWeeklyReport = lazyWithRetry(() => import('./boss').then(m => ({ default: m.AIWeeklyReport })));
const ExceptionQueue = lazyWithRetry(() => import('./boss').then(m => ({ default: m.ExceptionQueue })));
const TeamPerformanceHeatmap = lazyWithRetry(() => import('./boss').then(m => ({ default: m.TeamPerformanceHeatmap })));
const TopPerformers = lazyWithRetry(() => import('./boss').then(m => ({ default: m.TopPerformers })));

const SectionSkeleton = ({ className }: { className?: string }) => (
  <div className={cn("glass-premium rounded-3xl p-6 border-white/10", className)}>
    <Skeleton className="h-6 w-32 mb-4" />
    <Skeleton className="h-24 w-full" />
  </div>
);

export function BossDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const { user, role, loading } = useAuth();
  const { pendingApprovals, updateStatus } = useApprovals();

  const handleApprove = async (id: string) => {
    try {
      await updateStatus.mutateAsync({ id, status: 'approved' });
      toast.success('申请批准成功');
    } catch (e: unknown) {
      toast.error('操作失败: ' + (e instanceof Error ? e.message : '未知错误'));
    }
  };

  const handleReject = async (id: string) => {
    try {
      await updateStatus.mutateAsync({ id, status: 'rejected' });
      toast.success('申请已驳回');
    } catch (e: unknown) {
      toast.error('操作失败: ' + (e instanceof Error ? e.message : '未知错误'));
    }
  };

  useSalesMetricsRealtime();
  const { data: teamData } = useTeamPerformance();
  const { data: leaderboardData } = useLeaderboard(3);
  const seedDemoData = useSeedDemoData();

  const weeklyReport = useMemo(() => {
    if (!leaderboardData || leaderboardData.length === 0) return { totalIncentives: 0, topPerformers: [] };
    return {
      totalIncentives: leaderboardData.reduce((sum, p) => sum + p.bonus, 0),
      topPerformers: leaderboardData.map(p => ({
        name: p.name,
        score: p.score,
        bonus: p.bonus,
      })),
    };
  }, [leaderboardData]);

  const hasRealData = leaderboardData && leaderboardData.length > 0;

  if (!loading && !user) return <Navigate to="/login" replace />;
  if (!loading && role && !['boss', 'founder'].includes(role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="space-y-8 pb-12">
      {/* AI Quick Actions */}
      <AIQuickActions pageType="dashboard" />
      <LaunchChecklistPanel role={role || 'boss'} compact />

      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-[2.5rem] glass-premium p-8 sm:p-12 mb-8 animate-fade-slide-up">
        <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-primary/10 blur-[100px]" />
        <div className="absolute -bottom-24 -left-24 w-72 h-72 rounded-full bg-blue-500/5 blur-[80px]" />
        
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">
          <div className="space-y-4">
            <div className="flex items-center gap-5">
              <div className="p-4 rounded-2xl bg-gradient-primary shadow-xl ai-pulse-glow">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-4xl font-black tracking-tighter text-foreground">
                Nexus <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">COMMAND</span>
              </h1>
            </div>
            <p className="text-lg text-muted-foreground flex items-center gap-3 font-medium">
              <span className="flex h-3 w-3 rounded-full bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.5)]" />
              中枢系统已就绪 · <span className="text-foreground font-bold font-numbers">{pendingApprovals.length}</span> 项任务待审阅
            </p>
          </div>

          <div className="flex items-center gap-4">
            {!hasRealData && (
              <Button
                variant="outline"
                onClick={() => seedDemoData.mutateAsync()}
                className="command-capsule border-border hover:bg-muted h-14 px-8"
              >
                <Database className="w-5 h-5 mr-3 text-primary" />
                <span className="font-black text-xs uppercase tracking-widest text-muted-foreground">同步数据映射</span>
              </Button>
            )}
            <div className="h-14 px-8 glass-premium border-emerald-500/20 rounded-full flex items-center gap-4">
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest">Team Size</p>
                <p className="text-emerald-500 font-black font-numbers text-xl">{teamData?.length || 0}</p>
              </div>
              <div className="h-6 w-px bg-border" />
              <Activity className="w-6 h-6 text-emerald-500" />
            </div>
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="h-14 bg-muted border border-border p-1 rounded-2xl mb-8">
          <TabsTrigger value="overview" className="h-full px-8 rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-bold transition-all">
            <BarChart3 className="w-4 h-4 mr-2" /> 监控面板
          </TabsTrigger>
          <TabsTrigger value="history" className="h-full px-8 rounded-xl data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-bold transition-all">
            <History className="w-4 h-4 mr-2" /> 决策溯源
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-8 transition-all animate-fade-in">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-1 animate-fade-slide-up" style={{ animationDelay: '100ms' }}>
              <AlertWidget />
            </div>
            <div className="lg:col-span-3 animate-fade-slide-up" style={{ animationDelay: '200ms' }}>
              <AIActivityStats stats={{
                totalConversations: teamData?.length || 0,
                tasksHandled: weeklyReport.topPerformers.length * 12,
                avgConfidence: 0,
                responseTime: '--'
              }} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bento-card glass-premium rounded-[2.5rem] p-1 overflow-hidden animate-fade-slide-up hover-lift" style={{ animationDelay: '300ms' }}>
              <React.Suspense fallback={<SectionSkeleton />}>
                <RevenueChart />
              </React.Suspense>
            </div>
            <div className="bento-card glass-premium rounded-[2.5rem] p-1 overflow-hidden animate-fade-slide-up hover-lift" style={{ animationDelay: '400ms' }}>
              <React.Suspense fallback={<SectionSkeleton />}>
                <TeamPerformanceChart />
              </React.Suspense>
            </div>
          </div>

          <div className="bento-card glass-premium rounded-[2.5rem] overflow-hidden animate-fade-slide-up" style={{ animationDelay: '500ms' }}>
            <React.Suspense fallback={<SectionSkeleton />}>
              <ExceptionQueue
                pendingApprovals={pendingApprovals}
                onApprove={handleApprove}
                onReject={handleReject}
                isProcessing={updateStatus.isPending}
              />
            </React.Suspense>
          </div>
        </TabsContent>

        <TabsContent value="history" className="animate-fade-slide-up">
           <div className="glass-premium rounded-[2.5rem] p-8 border-border shadow-2xl">
              <SalesHistoryPanel />
           </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
