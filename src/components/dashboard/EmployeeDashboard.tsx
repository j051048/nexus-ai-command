import React, { useState, useEffect } from 'react';
import { useUser } from '@/contexts/UserContext';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  Award,
  Target,
  Zap,
  Trophy,
  Gift,
  ChevronRight,
  Star,
} from 'lucide-react';

const mockRankings = [
  { rank: 1, name: '王晓明', score: 95, bonus: 8200, trend: 'up' },
  { rank: 2, name: '刘芳', score: 91, bonus: 6800, trend: 'up' },
  { rank: 3, name: '张明', score: 87, bonus: 4850, trend: 'up', isCurrentUser: true },
  { rank: 4, name: '陈伟', score: 82, bonus: 3600, trend: 'down' },
  { rank: 5, name: '李娜', score: 78, bonus: 2900, trend: 'stable' },
];

const performanceMetrics = [
  { name: '跟进及时率', value: 92, target: 90, unit: '%', status: 'good' },
  { name: '通话质量分', value: 85, target: 80, unit: '', status: 'good' },
  { name: '赢率贡献', value: 23, target: 25, unit: '%', status: 'warning' },
  { name: '线索转化', value: 18, target: 15, unit: '%', status: 'excellent' },
];

export function EmployeeDashboard() {
  const { user } = useUser();
  const [animatedScore, setAnimatedScore] = useState(0);
  const [showBonusPopup, setShowBonusPopup] = useState(false);

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

  const progressToNextBadge = ((user.score - 80) / 20) * 100;

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            战绩中心
          </h1>
          <p className="text-muted-foreground mt-1">
            早上好，{user.name}！今天也要加油哦 💪
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-success/20 text-success hover:bg-success/30 transition-colors">
            <Gift className="w-4 h-4" />
            <span className="font-medium">¥{user.totalBonus.toLocaleString()}</span>
          </button>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-4 gap-4">
        {/* Score Card */}
        <div className="col-span-2 bg-gradient-card rounded-2xl p-6 cyber-border">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">今日AI绩效分</p>
              <div className="flex items-baseline gap-2 mt-2">
                <span className="text-5xl font-bold text-foreground mono-number score-up">
                  {animatedScore}
                </span>
                <span className="text-success text-sm font-medium flex items-center gap-1">
                  <TrendingUp className="w-4 h-4" />
                  +5
                </span>
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                  <span>距离"销售精英"徽章</span>
                  <span>{100 - user.score} 分</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-primary rounded-full progress-fill"
                    style={{ width: `${progressToNextBadge}%` }}
                  />
                </div>
              </div>
            </div>
            <div className="w-20 h-20 rounded-2xl bg-gradient-primary flex items-center justify-center glow-primary">
              <Award className="w-10 h-10 text-primary-foreground" />
            </div>
          </div>
        </div>

        {/* Rank Card */}
        <div className="bg-card rounded-2xl p-6 border border-border">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gold/20 flex items-center justify-center">
              <Trophy className="w-5 h-5 text-gold" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">本周排名</p>
              <p className="text-2xl font-bold text-foreground">第 {user.rank} 名</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            距离第2名还差 <span className="text-primary font-medium">150</span> 分
          </p>
        </div>

        {/* Bonus Card */}
        <div className="bg-card rounded-2xl p-6 border border-border">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-success/20 flex items-center justify-center">
              <Gift className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">累计奖金</p>
              <p className="text-2xl font-bold text-success mono-number">
                ¥{user.totalBonus.toLocaleString()}
              </p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            本月新增 <span className="text-success font-medium">¥2,200</span>
          </p>
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">绩效指标实时监控</h2>
          <span className="flex items-center gap-1 text-xs text-success">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
            实时更新
          </span>
        </div>
        <div className="grid grid-cols-4 gap-4">
          {performanceMetrics.map((metric) => (
            <div key={metric.name} className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{metric.name}</p>
                <span className={cn(
                  "text-xs font-medium px-2 py-0.5 rounded-full",
                  metric.status === 'excellent' && "bg-success/20 text-success",
                  metric.status === 'good' && "bg-primary/20 text-primary",
                  metric.status === 'warning' && "bg-warning/20 text-warning"
                )}>
                  {metric.status === 'excellent' ? '优秀' : metric.status === 'good' ? '达标' : '待提升'}
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold text-foreground mono-number">{metric.value}</span>
                <span className="text-sm text-muted-foreground">{metric.unit}</span>
                <span className="text-xs text-muted-foreground ml-1">/ {metric.target}{metric.unit}</span>
              </div>
              <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    metric.value >= metric.target ? "bg-success" : "bg-warning"
                  )}
                  style={{ width: `${Math.min((metric.value / metric.target) * 100, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Badges & Rankings Row */}
      <div className="grid grid-cols-2 gap-6">
        {/* Badges */}
        <div className="bg-card rounded-2xl p-6 border border-border">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">我的徽章</h2>
            <button className="text-xs text-primary hover:underline flex items-center gap-1">
              查看全部 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          <div className="flex gap-4">
            {user.badges.map((badge, index) => (
              <div
                key={badge.id}
                className={cn(
                  "flex flex-col items-center gap-2 p-4 rounded-xl transition-all",
                  badge.tier === 'gold' && "bg-gold/10",
                  badge.tier === 'silver' && "bg-silver/10",
                  badge.tier === 'bronze' && "bg-bronze/10",
                  index === 0 && "badge-unlock"
                )}
              >
                <span className="text-3xl">{badge.icon}</span>
                <span className="text-xs font-medium text-foreground">{badge.name}</span>
                <span className={cn(
                  "text-xs px-2 py-0.5 rounded-full",
                  badge.tier === 'gold' && "rank-gold",
                  badge.tier === 'silver' && "rank-silver",
                  badge.tier === 'bronze' && "rank-bronze"
                )}>
                  {badge.tier === 'gold' ? '金' : badge.tier === 'silver' ? '银' : '铜'}
                </span>
              </div>
            ))}
            <div className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl border-2 border-dashed border-border opacity-50">
              <Star className="w-8 h-8 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">待解锁</span>
            </div>
          </div>
        </div>

        {/* Rankings */}
        <div className="bg-card rounded-2xl p-6 border border-border">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">本周排行榜</h2>
            <span className="text-xs text-muted-foreground">实时更新</span>
          </div>
          <div className="space-y-3">
            {mockRankings.map((item) => (
              <div
                key={item.rank}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-xl transition-colors",
                  item.isCurrentUser ? "bg-primary/10 border border-primary/30" : "hover:bg-secondary"
                )}
              >
                <div className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold",
                  item.rank === 1 && "rank-gold",
                  item.rank === 2 && "rank-silver",
                  item.rank === 3 && "rank-bronze",
                  item.rank > 3 && "bg-secondary text-muted-foreground"
                )}>
                  {item.rank}
                </div>
                <div className="flex-1">
                  <p className={cn(
                    "text-sm font-medium",
                    item.isCurrentUser ? "text-primary" : "text-foreground"
                  )}>
                    {item.name} {item.isCurrentUser && "(我)"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-foreground mono-number">{item.score}</p>
                  <p className="text-xs text-success mono-number">¥{item.bonus.toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bonus Popup */}
      {showBonusPopup && (
        <div className="fixed inset-0 flex items-center justify-center z-[100] pointer-events-none">
          <div className="bg-card border-2 border-success rounded-3xl p-8 shadow-2xl glow-success bonus-popup">
            <div className="text-center">
              <div className="text-6xl mb-4">🎉</div>
              <h3 className="text-2xl font-bold text-foreground mb-2">即时奖金到账！</h3>
              <p className="text-4xl font-bold text-success mono-number mb-2">+¥200</p>
              <p className="text-muted-foreground">通话质量评分达到90+</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
