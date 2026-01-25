import React, { useState, useEffect, useMemo } from 'react';
import { useUser } from '@/contexts/UserContext';
import {
  TrendingUp,
  Zap,
  Gift,
  Plus,
  History,
  Database,
  Loader2,
} from 'lucide-react';
import { SalesChart, WinRateChart } from '@/components/charts';
import { useLeaderboard, useSalesMetrics, useSeedDemoData, useSalesMetricsRealtime } from '@/hooks/useSalesData';
import { SalesDataEntryForm, SalesHistoryPanel } from '@/components/sales';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  PerformanceScoreCard,
  StatCards,
  PerformanceMetricsMonitor,
  BadgePanel,
  WeeklyRankings
} from './employee';

const mockRankings = [
  { rank: 1, name: '王晓明', score: 95, bonus: 8200, trend: 'up' as const, isCurrentUser: false },
  { rank: 2, name: '刘芳', score: 91, bonus: 6800, trend: 'up' as const, isCurrentUser: false },
  { rank: 3, name: '张明', score: 87, bonus: 4850, trend: 'up' as const, isCurrentUser: true },
  { rank: 4, name: '陈伟', score: 82, bonus: 3600, trend: 'down' as const, isCurrentUser: false },
  { rank: 5, name: '李娜', score: 78, bonus: 2900, trend: 'stable' as const, isCurrentUser: false },
];

const defaultPerformanceMetrics = [
  { name: '跟进及时率', value: 92, target: 90, unit: '%', status: 'good' as const },
  { name: '通话质量分', value: 85, target: 80, unit: '', status: 'good' as const },
  { name: '赢率贡献', value: 23, target: 25, unit: '%', status: 'warning' as const },
  { name: '线索转化', value: 18, target: 15, unit: '%', status: 'excellent' as const },
];

export function EmployeeDashboard() {
  const { user } = useUser();
  const [animatedScore, setAnimatedScore] = useState(0);
  const [showBonusPopup, setShowBonusPopup] = useState(false);
  const [showEntryDialog, setShowEntryDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  // Enable realtime subscription for live updates
  useSalesMetricsRealtime();

  // Fetch real data from database
  const { data: leaderboardData } = useLeaderboard(5);
  const { data: salesMetrics } = useSalesMetrics(1); // Last month
  const seedDemoData = useSeedDemoData();

  // Use real rankings or fallback to mock
  const rankings = useMemo(() => {
    if (leaderboardData && leaderboardData.length > 0) {
      return leaderboardData;
    }
    return mockRankings;
  }, [leaderboardData]);

  // Calculate performance metrics from real data
  const performanceMetrics = useMemo(() => {
    if (!salesMetrics || salesMetrics.length === 0) {
      return defaultPerformanceMetrics;
    }

    const recent = salesMetrics.slice(-7); // Last 7 days
    const avgWinRate = recent.reduce((sum, m) => sum + (Number(m.win_rate) || 0), 0) / recent.length;
    const avgConversionRate = recent.reduce((sum, m) => {
      const leads = m.leads_count || 1;
      const conversions = m.conversions || 0;
      return sum + (conversions / leads) * 100;
    }, 0) / recent.length;

    return [
      { name: '跟进及时率', value: 92, target: 90, unit: '%', status: 'good' as const },
      { name: '通话质量分', value: 85, target: 80, unit: '', status: 'good' as const },
      { name: '赢率贡献', value: Math.round(avgWinRate), target: 25, unit: '%', status: avgWinRate >= 25 ? 'excellent' as const : 'warning' as const },
      { name: '线索转化', value: Math.round(avgConversionRate), target: 15, unit: '%', status: avgConversionRate >= 15 ? 'excellent' as const : 'good' as const },
    ];
  }, [salesMetrics]);

  const handleSeedData = async () => {
    try {
      await seedDemoData.mutateAsync();
      toast.success('已生成90天示例数据！');
    } catch (error: unknown) {
      const err = error as Error;
      toast.error('生成数据失败: ' + err.message);
    }
  };

  useEffect(() => {
    // Animate score counting up
    let current = 0;
    const target = user.score;
    const duration = 1000;
    const step = target / (duration / 16);

    const timer = setInterval(() => {
      current += step;
      if (current >= target) {
        setAnimatedScore(target);
        clearInterval(timer);
      } else {
        setAnimatedScore(Math.floor(current));
      }
    }, 16);

    return () => clearInterval(timer);
  }, [user.score]);

  // Simulate bonus popup
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowBonusPopup(true);
      setTimeout(() => setShowBonusPopup(false), 4000);
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  const hasRealData = salesMetrics && salesMetrics.length > 0;
  const progressToNextBadge = ((user.score - 80) / 20) * 100;

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-foreground">
            战绩中心
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">
            早上好，{user.name}！今天也要加油哦 💪
          </p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
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
          <Dialog open={showEntryDialog} onOpenChange={setShowEntryDialog}>
            <DialogTrigger asChild>
              <Button size="sm" className="flex items-center gap-2">
                <Plus className="w-4 h-4" />
                录入数据
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>录入销售数据</DialogTitle>
              </DialogHeader>
              <SalesDataEntryForm onSuccess={() => setShowEntryDialog(false)} />
            </DialogContent>
          </Dialog>
          <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-success/20 text-success hover:bg-success/30 transition-colors">
            <Gift className="w-4 h-4" />
            <span className="font-medium">¥{user.totalBonus.toLocaleString()}</span>
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 sm:w-auto sm:inline-flex">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            概览
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <History className="w-4 h-4" />
            历史查询
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 sm:space-y-6 mt-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <PerformanceScoreCard
              score={user.score}
              animatedScore={animatedScore}
              progressToNextBadge={progressToNextBadge}
            />
            <StatCards rank={user.rank} totalBonus={user.totalBonus} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            <SalesChart />
            <WinRateChart />
          </div>

          <PerformanceMetricsMonitor metrics={performanceMetrics} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            <BadgePanel badges={user.badges} />
            <WeeklyRankings rankings={rankings} />
          </div>
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <SalesHistoryPanel />
        </TabsContent>
      </Tabs>

      {/* Bonus Popup */}
      {showBonusPopup && (
        <div className="fixed inset-0 flex items-center justify-center z-[100] pointer-events-none p-4">
          <div className="bg-card border-2 border-success rounded-3xl p-6 sm:p-8 shadow-2xl glow-success bonus-popup max-w-sm w-full">
            <div className="text-center">
              <div className="text-5xl sm:text-6xl mb-4">🎉</div>
              <h3 className="text-xl sm:text-2xl font-bold text-foreground mb-2">即时奖金到账！</h3>
              <p className="text-3xl sm:text-4xl font-bold text-success mono-number mb-2">+¥200</p>
              <p className="text-sm text-muted-foreground">通话质量评分达到90+</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
