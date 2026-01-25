import React from 'react';
import { useUser } from '@/contexts/UserContext';
import { cn } from '@/lib/utils';
import {
  Wallet,
  TrendingUp,
  Gift,
  Trophy,
  Star,
  ChevronRight,
  Clock,
  CheckCircle2,
} from 'lucide-react';

const recentBonuses = [
  { id: '1', reason: '商机推进至技术验证', amount: 300, time: '2小时前', icon: '🎯' },
  { id: '2', reason: '通话质量评分90+', amount: 200, time: '今天', icon: '📞' },
  { id: '3', reason: '连续5日跟进达标', amount: 200, time: '昨天', icon: '🔥' },
  { id: '4', reason: '新客户首次成单', amount: 500, time: '3天前', icon: '🎉' },
  { id: '5', reason: '周排行榜前三', amount: 300, time: '上周', icon: '🏆' },
];

const achievements = [
  { id: '1', name: '学术猎手', description: '成功转化3位教授客户', icon: '🎯', tier: 'gold', progress: 100 },
  { id: '2', name: '话术大师', description: 'AI通话评分连续5次90+', icon: '💬', tier: 'silver', progress: 100 },
  { id: '3', name: '速战速决', description: '平均响应时间<2小时', icon: '⚡', tier: 'bronze', progress: 100 },
  { id: '4', name: '销售精英', description: '月度绩效分达到95+', icon: '👑', tier: 'gold', progress: 65 },
  { id: '5', name: '客户之友', description: '获得10个客户好评', icon: '❤️', tier: 'silver', progress: 40 },
];

export function RewardsWallet() {
  const { user } = useUser();

  const pendingWithdraw = 2200;
  const totalEarned = 12850;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">激励钱包</h1>
        <p className="text-muted-foreground mt-1">您的成就与奖励中心</p>
      </div>

      {/* Wallet Overview */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-gradient-card rounded-2xl p-6 cyber-border">
          <div className="flex items-start justify-between mb-6">
            <div>
              <p className="text-sm text-muted-foreground">累计奖金余额</p>
              <p className="text-4xl font-bold text-foreground mono-number mt-2">
                ¥{user.totalBonus.toLocaleString()}
              </p>
              <div className="flex items-center gap-4 mt-3">
                <span className="text-sm text-muted-foreground">
                  待提现 <span className="text-success font-medium">¥{pendingWithdraw.toLocaleString()}</span>
                </span>
                <span className="text-sm text-muted-foreground">
                  累计获得 <span className="text-foreground font-medium">¥{totalEarned.toLocaleString()}</span>
                </span>
              </div>
            </div>
            <div className="w-16 h-16 rounded-2xl bg-gradient-success flex items-center justify-center glow-success">
              <Wallet className="w-8 h-8 text-white" />
            </div>
          </div>
          <button className="w-full py-3 rounded-xl bg-success text-white font-medium hover:bg-success/90 transition-colors">
            申请提现
          </button>
        </div>

        <div className="bg-card rounded-2xl p-6 border border-border flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-5 h-5 text-success" />
              <span className="text-sm text-muted-foreground">本月收益</span>
            </div>
            <p className="text-3xl font-bold text-success mono-number">+¥2,200</p>
          </div>
          <div className="pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground">较上月</p>
            <p className="text-sm font-medium text-success flex items-center gap-1">
              <TrendingUp className="w-4 h-4" />
              +18.5%
            </p>
          </div>
        </div>
      </div>

      {/* Recent Bonuses */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">奖金明细</h2>
          <button className="text-sm text-primary hover:underline flex items-center gap-1">
            查看全部 <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          {recentBonuses.map((bonus, index) => (
            <div
              key={bonus.id}
              className={cn(
                "flex items-center gap-4 p-4 rounded-xl transition-colors",
                index === 0 ? "bg-success/10 border border-success/30" : "bg-secondary/50 hover:bg-secondary"
              )}
            >
              <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center text-2xl">
                {bonus.icon}
              </div>
              <div className="flex-1">
                <p className="font-medium text-foreground">{bonus.reason}</p>
                <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                  <Clock className="w-3 h-3" />
                  {bonus.time}
                </p>
              </div>
              <p className={cn(
                "text-lg font-bold mono-number",
                index === 0 ? "text-success" : "text-foreground"
              )}>
                +¥{bonus.amount}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Achievements */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">成就系统</h2>
          <span className="text-sm text-muted-foreground">
            已解锁 <span className="text-foreground font-medium">3/5</span>
          </span>
        </div>

        <div className="grid grid-cols-5 gap-4">
          {achievements.map((achievement) => (
            <div
              key={achievement.id}
              className={cn(
                "relative p-4 rounded-xl border transition-all",
                achievement.progress === 100
                  ? "border-gold/50 bg-gold/5"
                  : "border-border bg-secondary/30 opacity-60"
              )}
            >
              {achievement.progress === 100 && (
                <div className="absolute -top-2 -right-2">
                  <CheckCircle2 className="w-5 h-5 text-success" />
                </div>
              )}
              
              <div className="text-center">
                <div className={cn(
                  "w-14 h-14 rounded-2xl mx-auto flex items-center justify-center text-3xl mb-3",
                  achievement.progress === 100 ? "bg-gold/20" : "bg-muted"
                )}>
                  {achievement.icon}
                </div>
                <p className="font-medium text-foreground text-sm">{achievement.name}</p>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{achievement.description}</p>
                
                {achievement.progress < 100 && (
                  <div className="mt-3">
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${achievement.progress}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{achievement.progress}%</p>
                  </div>
                )}

                {achievement.progress === 100 && (
                  <span className={cn(
                    "inline-block mt-3 px-2 py-0.5 rounded-full text-xs font-medium",
                    achievement.tier === 'gold' && "rank-gold",
                    achievement.tier === 'silver' && "rank-silver",
                    achievement.tier === 'bronze' && "rank-bronze"
                  )}>
                    {achievement.tier === 'gold' ? '金' : achievement.tier === 'silver' ? '银' : '铜'}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Incentive Rules */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">激励规则</h2>
          <Gift className="w-5 h-5 text-primary" />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-secondary/50">
            <p className="text-success font-bold text-xl mb-2">+¥500</p>
            <p className="text-sm text-foreground font-medium">新客户首次成单</p>
            <p className="text-xs text-muted-foreground mt-1">客户首次下单后触发</p>
          </div>
          <div className="p-4 rounded-xl bg-secondary/50">
            <p className="text-success font-bold text-xl mb-2">+¥300</p>
            <p className="text-sm text-foreground font-medium">商机推进至技术验证</p>
            <p className="text-xs text-muted-foreground mt-1">商机阶段变更触发</p>
          </div>
          <div className="p-4 rounded-xl bg-secondary/50">
            <p className="text-success font-bold text-xl mb-2">+¥200</p>
            <p className="text-sm text-foreground font-medium">通话质量评分90+</p>
            <p className="text-xs text-muted-foreground mt-1">AI实时评分触发</p>
          </div>
          <div className="p-4 rounded-xl bg-secondary/50">
            <p className="text-success font-bold text-xl mb-2">+¥200</p>
            <p className="text-sm text-foreground font-medium">连续5日跟进达标</p>
            <p className="text-xs text-muted-foreground mt-1">每日跟进≥3个线索</p>
          </div>
          <div className="p-4 rounded-xl bg-secondary/50">
            <p className="text-success font-bold text-xl mb-2">+¥100</p>
            <p className="text-sm text-foreground font-medium">每日跟进达标</p>
            <p className="text-xs text-muted-foreground mt-1">当日跟进≥3个线索</p>
          </div>
          <div className="p-4 rounded-xl bg-secondary/50">
            <p className="text-gold font-bold text-xl mb-2">红包</p>
            <p className="text-sm text-foreground font-medium">月度排行前三</p>
            <p className="text-xs text-muted-foreground mt-1">额外现金红包奖励</p>
          </div>
        </div>
      </div>
    </div>
  );
}
