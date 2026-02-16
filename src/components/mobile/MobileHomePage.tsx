import { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  ClipboardCheck,
  Users,
  TrendingUp,
  Target,
  BookOpen,
  MoreHorizontal,
  AlertTriangle,
  Trophy,
  Medal,
  DollarSign,
  Brain,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { usePendingApprovalsCount } from '@/hooks/useApprovals';
import { usePullToRefresh } from '@/hooks/usePullToRefresh';
import { PullToRefreshIndicator } from '@/components/common/PullToRefreshIndicator';

/** 获取时段问候语 */
function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return '夜深了';
  if (hour < 12) return '早上好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
}

/** 快捷入口定义 */
interface QuickEntry {
  id: string;
  label: string;
  icon: React.ElementType;
  path: string;
  color: string;
  bgColor: string;
}

export default function MobileHomePage() {
  const { user } = useUser();
  const { role } = useAuth();
  const pendingApprovalsQuery = usePendingApprovalsCount();
  const pendingCount = pendingApprovalsQuery.data ?? 0;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const isBoss = role === 'boss';

  // 下拉刷新
  const handleRefresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['approvals'] });
  }, [queryClient]);

  const { isRefreshing, pullDistance, containerRef, handlers } = usePullToRefresh({
    onRefresh: handleRefresh,
    threshold: 80,
  });

  // 快捷入口配置 - Boss 角色差异化
  const quickEntries: QuickEntry[] = useMemo(() => {
    const base: QuickEntry[] = [
      {
        id: 'approval',
        label: '审批',
        icon: ClipboardCheck,
        path: '/approval',
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
      },
      isBoss
        ? {
            id: 'anomaly',
            label: '异常待办',
            icon: AlertTriangle,
            path: '/approval?status=pending',
            color: 'text-red-600',
            bgColor: 'bg-red-50',
          }
        : {
            id: 'crm',
            label: 'CRM',
            icon: Users,
            path: '/crm',
            color: 'text-purple-600',
            bgColor: 'bg-purple-50',
          },
      {
        id: 'sales',
        label: '销售',
        icon: TrendingUp,
        path: '/sales',
        color: 'text-green-600',
        bgColor: 'bg-green-50',
      },
      {
        id: 'targets',
        label: '目标',
        icon: Target,
        path: '/targets',
        color: 'text-orange-600',
        bgColor: 'bg-orange-50',
      },
      {
        id: 'knowledge',
        label: '知识库',
        icon: BookOpen,
        path: '/knowledge',
        color: 'text-cyan-600',
        bgColor: 'bg-cyan-50',
      },
      {
        id: 'more',
        label: '更多',
        icon: MoreHorizontal,
        path: '/dashboard',
        color: 'text-gray-600',
        bgColor: 'bg-gray-100',
      },
    ];
    return base;
  }, [isBoss]);

  // 指标数据
  const metrics = useMemo(
    () => [
      {
        id: 'score',
        label: '绩效分',
        value: `${user.score}`,
        unit: '/100',
        icon: Trophy,
        color: 'text-amber-600',
        bgColor: 'bg-amber-50',
      },
      {
        id: 'rank',
        label: '排名',
        value: `第${user.rank}名`,
        unit: '',
        icon: Medal,
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
      },
      {
        id: 'bonus',
        label: '奖金',
        value: `¥${user.totalBonus.toLocaleString()}`,
        unit: '',
        icon: DollarSign,
        color: 'text-green-600',
        bgColor: 'bg-green-50',
      },
      {
        id: 'ai-score',
        label: 'AI 评分',
        value: '87',
        unit: '分',
        icon: Brain,
        color: 'text-violet-600',
        bgColor: 'bg-violet-50',
      },
    ],
    [user.score, user.rank, user.totalBonus]
  );

  // 待办事项
  const todoItems = useMemo(() => {
    const items: { id: string; label: string; count: number; path: string }[] = [];
    if (pendingCount > 0) {
      items.push({
        id: 'pending-approvals',
        label: '审批待处理',
        count: pendingCount,
        path: '/approval',
      });
    }
    return items;
  }, [pendingCount]);

  return (
    <div
      ref={containerRef}
      className="h-full overflow-y-auto bg-gray-50"
      {...handlers}
    >
      {/* 下拉刷新指示器 */}
      <PullToRefreshIndicator
        pullDistance={pullDistance}
        isRefreshing={isRefreshing}
        threshold={80}
      />

      <div className="px-4 pb-24 space-y-4">
        {/* ===== AI 摘要卡片 ===== */}
        <section className="relative mt-4 overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-5 text-white shadow-lg">
          {/* 装饰元素 */}
          <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-white/10" />
          <div className="absolute -bottom-4 -left-4 h-16 w-16 rounded-full bg-white/10" />

          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-5 w-5 text-yellow-200" />
              <span className="text-xs font-medium uppercase tracking-wider text-white/80">
                AI 日报
              </span>
            </div>
            <h2 className="text-xl font-bold leading-snug">
              {getGreeting()}，{user.name}！
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-white/90">
              {isBoss ? (
                <>
                  团队今日概览：
                  {pendingCount > 0
                    ? `${pendingCount} 条审批待您决策`
                    : '所有审批已处理完毕'}
                  ，团队绩效稳步上升。
                </>
              ) : (
                <>
                  今日关键提醒：
                  {pendingCount > 0
                    ? `${pendingCount} 条审批待处理`
                    : '暂无待处理审批'}
                  ，继续保持好状态！
                </>
              )}
            </p>
          </div>
        </section>

        {/* ===== 关键指标 2x2 ===== */}
        <section>
          <h3 className="mb-3 text-sm font-semibold text-gray-500">关键指标</h3>
          <div className="grid grid-cols-2 gap-3">
            {metrics.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-3 rounded-xl bg-white p-4 shadow-sm"
              >
                <div
                  className={cn(
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                    m.bgColor
                  )}
                >
                  <m.icon className={cn('h-5 w-5', m.color)} />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-lg font-bold text-gray-900">
                    {m.value}
                    {m.unit && (
                      <span className="text-xs font-normal text-gray-400">
                        {m.unit}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-gray-500">{m.label}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ===== 快捷入口 3x2 ===== */}
        <section>
          <h3 className="mb-3 text-sm font-semibold text-gray-500">快捷入口</h3>
          <div className="grid grid-cols-3 gap-3">
            {quickEntries.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => navigate(entry.path)}
                className="flex flex-col items-center gap-2 rounded-xl bg-white p-4 shadow-sm transition-transform active:scale-95"
              >
                <div
                  className={cn(
                    'flex h-11 w-11 items-center justify-center rounded-xl',
                    entry.bgColor
                  )}
                >
                  <entry.icon className={cn('h-5 w-5', entry.color)} />
                </div>
                <span className="text-xs font-medium text-gray-700">
                  {entry.label}
                </span>
              </button>
            ))}
          </div>
        </section>

        {/* ===== 待办速览 ===== */}
        <section>
          <h3 className="mb-3 text-sm font-semibold text-gray-500">待办速览</h3>
          {todoItems.length > 0 ? (
            <div className="space-y-2">
              {todoItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigate(item.path)}
                  className="flex w-full items-center justify-between rounded-xl bg-white px-4 py-3 shadow-sm transition-colors active:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-50">
                      <ClipboardCheck className="h-4 w-4 text-red-500" />
                    </span>
                    <span className="text-sm font-medium text-gray-800">
                      {item.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-red-500 px-2.5 py-0.5 text-xs font-semibold text-white">
                      {item.count}
                    </span>
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl bg-white py-8 shadow-sm">
              <ClipboardCheck className="mb-2 h-8 w-8 text-gray-300" />
              <p className="text-sm text-gray-400">暂无待办事项</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
