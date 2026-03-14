import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import {
  Wallet,
  Award,
  Settings,
  Moon,
  ShieldCheck,
  CreditCard,
  HelpCircle,
  MessageSquare,
  LogOut,
  ChevronRight,
  Trophy,
  Medal,
  DollarSign,
  GraduationCap,
  Puzzle,
  LayoutDashboard,
  Crown,
  KeyRound,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUser } from '@/contexts/UserContext';
import { useAuth } from '@/components/auth/AuthContext';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { toast } from '@/hooks/use-toast';

/** 角色中文映射 */
const ROLE_LABEL: Record<string, string> = {
  boss: '老板',
  manager: '管理者',
  employee: '员工',
};

/** 功能列表项定义 */
interface MenuItem {
  id: string;
  label: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  /** 点击行为：路由跳转 */
  path?: string;
  /** 点击行为：自定义动作 */
  action?: () => void;
  /** 右侧放自定义组件替代箭头 */
  trailing?: React.ReactNode;
  /** 是否仅 boss 可见 */
  bossOnly?: boolean;
}

export default function MobileProfilePage() {
  const { user } = useUser();
  const { role, signOut } = useAuth();
  const navigate = useNavigate();

  const isBoss = role === 'boss';

  // 数据快照
  const stats = useMemo(
    () => [
      {
        id: 'score',
        label: '积分',
        value: `${user.score}`,
        icon: Trophy,
        color: 'text-amber-600',
        bg: 'bg-amber-50',
      },
      {
        id: 'rank',
        label: '排名',
        value: `第${user.rank}名`,
        icon: Medal,
        color: 'text-blue-600',
        bg: 'bg-blue-50',
      },
      {
        id: 'bonus',
        label: '奖金',
        value: `¥${user.totalBonus.toLocaleString()}`,
        icon: DollarSign,
        color: 'text-green-600',
        bg: 'bg-green-50',
      },
    ],
    [user.score, user.rank, user.totalBonus]
  );

  // 功能列表
  const menuItems: MenuItem[] = useMemo(
    () => [
      {
        id: 'rewards',
        label: '激励钱包',
        icon: Wallet,
        iconColor: 'text-orange-600',
        iconBg: 'bg-orange-50 dark:bg-orange-900/20',
        path: '/rewards',
      },
      {
        id: 'badges',
        label: '成就徽章',
        icon: Award,
        iconColor: 'text-purple-600',
        iconBg: 'bg-purple-50 dark:bg-purple-900/20',
        path: '/rewards',
      },
      {
        id: 'ai-settings',
        label: '系统设置',
        icon: Settings,
        iconColor: 'text-gray-600 dark:text-gray-400',
        iconBg: 'bg-gray-100 dark:bg-gray-800',
        path: '/settings',
      },
      {
        id: 'training',
        label: '培训中心',
        icon: GraduationCap,
        iconColor: 'text-blue-600',
        iconBg: 'bg-blue-50 dark:bg-blue-900/20',
        path: '/training',
      },
      {
        id: 'dark-mode',
        label: '深色模式',
        icon: Moon,
        iconColor: 'text-indigo-600',
        iconBg: 'bg-indigo-50 dark:bg-indigo-900/20',
        trailing: <ThemeToggle />,
      },
      {
        id: 'custom-dashboard',
        label: '自定义看板',
        icon: LayoutDashboard,
        iconColor: 'text-emerald-600',
        iconBg: 'bg-emerald-50 dark:bg-emerald-900/20',
        path: '/custom-dashboard',
        bossOnly: true,
      },
      {
        id: 'audit',
        label: '审计日志',
        icon: ShieldCheck,
        iconColor: 'text-red-600',
        iconBg: 'bg-red-50 dark:bg-red-900/20',
        path: '/audit',
        bossOnly: true,
      },
      {
        id: 'payments',
        label: '订阅支付',
        icon: CreditCard,
        iconColor: 'text-teal-600',
        iconBg: 'bg-teal-50 dark:bg-teal-900/20',
        path: '/payments',
        bossOnly: true,
      },
      {
        id: 'plugins',
        label: '插件市场',
        icon: Puzzle,
        iconColor: 'text-violet-600',
        iconBg: 'bg-violet-50 dark:bg-violet-900/20',
        path: '/plugins',
        bossOnly: true,
      },
      {
        id: 'api-keys',
        label: 'API 密钥',
        icon: KeyRound,
        iconColor: 'text-amber-600',
        iconBg: 'bg-amber-50 dark:bg-amber-900/20',
        path: '/api-keys',
        bossOnly: true,
      },
      {
        id: 'super-admin',
        label: '超管面板',
        icon: Crown,
        iconColor: 'text-yellow-600',
        iconBg: 'bg-yellow-50 dark:bg-yellow-900/20',
        path: '/super-admin',
        bossOnly: true,
      },
      {
        id: 'help',
        label: '帮助中心',
        icon: HelpCircle,
        iconColor: 'text-cyan-600',
        iconBg: 'bg-cyan-50 dark:bg-cyan-900/20',
        action: () => {
          toast({ title: '帮助中心', description: '该功能即将上线，敬请期待' });
        },
      },
      {
        id: 'feedback',
        label: '意见反馈',
        icon: MessageSquare,
        iconColor: 'text-pink-600',
        iconBg: 'bg-pink-50 dark:bg-pink-900/20',
        action: () => {
          toast({ title: '意见反馈', description: '该功能即将上线，敬请期待' });
        },
      },
    ],
    []
  );

  // 过滤 bossOnly 项
  const visibleItems = useMemo(
    () => menuItems.filter((item) => !item.bossOnly || isBoss),
    [menuItems, isBoss]
  );

  /** 头像首字母 fallback */
  const avatarInitial = user.name?.charAt(0) || '?';
  const [avatarError, setAvatarError] = useState(false);

  /** 处理菜单项点击 */
  const handleItemClick = (item: MenuItem) => {
    if (item.trailing) return; // 有 trailing 组件的不做跳转
    if (item.path) {
      navigate(item.path);
    } else if (item.action) {
      item.action();
    }
  };

  /** 退出登录 */
  const { confirm, ConfirmDialogProps } = useConfirmDialog();
  const handleSignOut = async () => {
    const ok = await confirm({
      title: '确认退出登录',
      description: '退出后需要重新登录才能访问系统，确定要继续吗？',
      confirmText: '退出登录',
      variant: 'destructive',
    });
    if (ok) {
      await signOut();
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-gray-50 dark:bg-background">
      <div className="px-4 pb-24 space-y-4">
        {/* ===== 用户信息卡片 ===== */}
        <section className="relative mt-4 overflow-hidden rounded-2xl bg-gradient-to-br from-primary to-primary/70 p-5 text-white shadow-lg">
          {/* 装饰元素 */}
          <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-white/10" />
          <div className="absolute -bottom-4 -left-4 h-16 w-16 rounded-full bg-white/10" />

          <div className="relative z-10 flex items-center gap-4">
            {/* 头像 */}
            {user.avatar && !avatarError ? (
              <img
                src={user.avatar}
                alt={user.name}
                loading="lazy"
                onError={() => setAvatarError(true)}
                className="h-16 w-16 shrink-0 rounded-full border-2 border-white/30 object-cover"
              />
            ) : (
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-2 border-white/30 bg-white/20 text-2xl font-bold">
                {avatarInitial}
              </div>
            )}

            {/* 姓名 + 部门 + 角色 */}
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-bold leading-snug">
                {user.name}
              </h2>
              <p className="mt-0.5 truncate text-sm text-white/80">
                {user.department}
              </p>
              <span className="mt-1.5 inline-block rounded-full bg-white/20 px-3 py-0.5 text-xs font-medium backdrop-blur-sm">
                {ROLE_LABEL[role || 'employee'] || '员工'}
              </span>
            </div>
          </div>
        </section>

        {/* ===== 数据快照卡片 ===== */}
        <section className="grid grid-cols-3 gap-3">
          {stats.map((s) => (
            <div
              key={s.id}
              className="flex flex-col items-center gap-1.5 rounded-xl bg-white p-4 border border-border/40 dark:bg-card"
            >
              <div
                className={cn(
                  'flex h-9 w-9 items-center justify-center rounded-lg',
                  s.bg
                )}
              >
                <s.icon className={cn('h-5 w-5', s.color)} />
              </div>
              <p className="text-base font-bold text-gray-900 dark:text-foreground">
                {s.value}
              </p>
              <p className="text-xs text-gray-500 dark:text-muted-foreground">
                {s.label}
              </p>
            </div>
          ))}
        </section>

        {/* ===== 功能列表 ===== */}
        <section className="overflow-hidden rounded-xl bg-white border border-border/40 dark:bg-card">
          {visibleItems.map((item, index) => (
            <button
              key={item.id}
              type="button"
              onClick={() => handleItemClick(item)}
              className={cn(
                'flex w-full items-center justify-between px-4 py-3.5 transition-colors active:bg-gray-50 dark:active:bg-muted',
                index !== visibleItems.length - 1 &&
                  'border-b border-gray-100 dark:border-border'
              )}
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                    item.iconBg
                  )}
                >
                  <item.icon className={cn('h-5 w-5', item.iconColor)} />
                </div>
                <span className="text-sm font-medium text-gray-800 dark:text-foreground">
                  {item.label}
                </span>
              </div>

              {/* 右侧：自定义 trailing 或箭头 */}
              {item.trailing ? (
                <div onClick={(e) => e.stopPropagation()}>{item.trailing}</div>
              ) : (
                <ChevronRight className="h-4 w-4 text-gray-400" />
              )}
            </button>
          ))}
        </section>

        {/* ===== 退出登录 ===== */}
        <section>
          <button
            type="button"
            onClick={handleSignOut}
            className="flex w-full items-center justify-center rounded-xl bg-white py-3.5 border border-border/40 transition-colors active:bg-gray-50 dark:bg-card dark:active:bg-muted"
          >
            <LogOut className="mr-2 h-4 w-4 text-red-500" />
            <span className="text-sm font-medium text-red-500">退出登录</span>
          </button>
        </section>
      </div>
      <ConfirmDialog {...ConfirmDialogProps} />
    </div>
  );
}
