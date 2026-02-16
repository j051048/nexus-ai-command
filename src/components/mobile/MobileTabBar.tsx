/**
 * 移动端底部 Tab 导航栏
 * 5-tab: 首页 | 工作台 | AI(中心突出) | 消息 | 我的
 * AI Tab 不跳路由，唤起半屏浮窗
 */

import { Home, LayoutGrid, Bot, Bell, User } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TabDef {
  id: string;
  label: string;
  icon: React.ElementType;
  isCenter?: boolean;
}

const TABS: TabDef[] = [
  { id: 'home', label: '首页', icon: Home },
  { id: 'workbench', label: '工作台', icon: LayoutGrid },
  { id: 'ai', label: 'AI', icon: Bot, isCenter: true },
  { id: 'notifications', label: '消息', icon: Bell },
  { id: 'profile', label: '我的', icon: User },
];

interface MobileTabBarProps {
  activeTab: string;
  onTabChange: (tabId: string) => void;
  onAIPress: () => void;
  pendingCount?: number;
  unreadCount?: number;
}

export default function MobileTabBar({
  activeTab,
  onTabChange,
  onAIPress,
  pendingCount = 0,
  unreadCount = 0,
}: MobileTabBarProps) {
  const handlePress = (tab: TabDef) => {
    if (tab.id === 'ai') {
      onAIPress();
    } else {
      onTabChange(tab.id);
    }
  };

  return (
    <nav
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50',
        'bg-background/95 backdrop-blur-md border-t border-border',
        'pb-[env(safe-area-inset-bottom)]',
        'md:hidden'
      )}
    >
      <div className="flex items-center justify-around h-14">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;

          // Badge 计算
          let badgeCount = 0;
          if (tab.id === 'workbench') badgeCount = pendingCount;
          if (tab.id === 'notifications') badgeCount = unreadCount;

          // AI 中心按钮 — 突出样式
          if (tab.isCenter) {
            return (
              <button
                key={tab.id}
                onClick={() => handlePress(tab)}
                className={cn(
                  'flex flex-col items-center justify-center',
                  'w-full h-full min-w-[44px] min-h-[44px]',
                  'transition-all duration-200',
                  'active:scale-95 touch-manipulation',
                  '-mt-3'
                )}
                aria-label={tab.label}
              >
                <div
                  className={cn(
                    'w-11 h-11 rounded-full flex items-center justify-center shadow-lg transition-all',
                    'bg-primary text-primary-foreground hover:bg-primary/90'
                  )}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-[10px] leading-tight mt-0.5 text-muted-foreground">
                  {tab.label}
                </span>
              </button>
            );
          }

          return (
            <button
              key={tab.id}
              onClick={() => handlePress(tab)}
              className={cn(
                'flex flex-col items-center justify-center gap-0.5',
                'w-full h-full min-w-[44px] min-h-[44px]',
                'transition-colors duration-200',
                'active:scale-95 touch-manipulation',
                isActive
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              aria-label={tab.label}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="relative">
                <Icon className={cn('w-5 h-5', isActive && 'stroke-[2.5]')} />
                {badgeCount > 0 && (
                  <span
                    className={cn(
                      'absolute -top-1.5 -right-2.5 min-w-[16px] h-4',
                      'flex items-center justify-center',
                      'rounded-full bg-destructive text-destructive-foreground',
                      'text-[10px] font-medium px-1 leading-none'
                    )}
                  >
                    {badgeCount > 99 ? '99+' : badgeCount}
                  </span>
                )}
              </div>
              <span className={cn('text-[10px] leading-tight', isActive && 'font-medium')}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
