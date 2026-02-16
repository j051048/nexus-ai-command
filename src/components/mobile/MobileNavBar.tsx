import { useState } from 'react';
import { Home, LayoutGrid, MessageCircle, Bell, User, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';

/** 底部导航栏 Tab 定义 */
interface NavTab {
  id: string;
  label: string;
  icon: React.ElementType;
  path: string;
  badge?: number;
  isCenter?: boolean;
}

interface MobileNavBarProps {
  /** 当前激活的 tab id */
  activeTab?: string;
  /** Tab 切换回调 */
  onTabChange?: (tabId: string, path: string) => void;
  /** 未读通知数 */
  unreadCount?: number;
}

const NAV_TABS: NavTab[] = [
  { id: 'home', label: '首页', icon: Home, path: '/dashboard' },
  { id: 'workbench', label: '工作台', icon: LayoutGrid, path: '/approval' },
  { id: 'chat', label: 'AI', icon: Bot, path: '/', isCenter: true },
  { id: 'notifications', label: '消息', icon: Bell, path: '/notification-center' },
  { id: 'profile', label: '我的', icon: User, path: '/profile' },
];

/**
 * 移动端底部导航栏
 * 5-tab 结构：首页 | 工作台 | AI(中心突出) | 消息 | 我的
 * 仅在 md (768px) 以下屏幕显示
 */
export default function MobileNavBar({
  activeTab: controlledTab,
  onTabChange,
  unreadCount = 0,
}: MobileNavBarProps) {
  const [internalTab, setInternalTab] = useState('home');
  const activeTab = controlledTab ?? internalTab;

  const handleTabClick = (tab: NavTab) => {
    setInternalTab(tab.id);
    onTabChange?.(tab.id, tab.path);
  };

  return (
    <nav
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50',
        'bg-background/95 backdrop-blur-md border-t border-border',
        'md:hidden', // 仅移动端显示
        'pb-[env(safe-area-inset-bottom)]'
      )}
    >
      <div className="flex items-center justify-around h-14">
        {NAV_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          const showBadge = tab.id === 'notifications' && unreadCount > 0;

          // AI 中心按钮 — 突出样式
          if (tab.isCenter) {
            return (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab)}
                className={cn(
                  'flex flex-col items-center justify-center',
                  'w-full h-full min-w-[44px] min-h-[44px]',
                  'transition-all duration-200',
                  'active:scale-95 touch-manipulation',
                  '-mt-3' // 向上突出
                )}
                aria-label={tab.label}
                aria-current={isActive ? 'page' : undefined}
              >
                <div
                  className={cn(
                    'w-11 h-11 rounded-full flex items-center justify-center shadow-lg transition-all',
                    isActive
                      ? 'bg-primary text-primary-foreground scale-105 shadow-primary/30'
                      : 'bg-primary/90 text-primary-foreground hover:bg-primary'
                  )}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <span className={cn(
                  'text-[10px] leading-tight mt-0.5',
                  isActive ? 'text-primary font-medium' : 'text-muted-foreground'
                )}>
                  {tab.label}
                </span>
              </button>
            );
          }

          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab)}
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
                {showBadge && (
                  <span
                    className={cn(
                      'absolute -top-1.5 -right-2 min-w-[16px] h-4',
                      'flex items-center justify-center',
                      'rounded-full bg-destructive text-destructive-foreground',
                      'text-[10px] font-medium px-1 leading-none'
                    )}
                  >
                    {unreadCount > 99 ? '99+' : unreadCount}
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
