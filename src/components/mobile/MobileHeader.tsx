import { Menu, Search, Bell } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface MobileHeaderProps {
  /** 页面标题 */
  title?: string;
  /** 切换侧边栏回调 */
  onMenuToggle?: () => void;
  /** 搜索按钮回调 */
  onSearchClick?: () => void;
  /** 通知按钮回调 */
  onNotificationClick?: () => void;
  /** 未读通知数 */
  unreadCount?: number;
  /** 是否显示搜索按钮 */
  showSearch?: boolean;
}

/**
 * 移动端顶部导航栏
 * 左侧: 汉堡菜单按钮（切换侧边栏）
 * 中间: 页面标题
 * 右侧: 搜索按钮 + 通知铃铛
 * 仅在 md 以下屏幕显示
 */
export default function MobileHeader({
  title = 'Nexus AI',
  onMenuToggle,
  onSearchClick,
  onNotificationClick,
  unreadCount = 0,
  showSearch = true,
}: MobileHeaderProps) {
  return (
    <header
      className={cn(
        'fixed top-0 left-0 right-0 z-50',
        'bg-background/95 backdrop-blur-md border-b border-border',
        'md:hidden', // 仅移动端显示
        'pt-[env(safe-area-inset-top)]'
      )}
    >
      <div className="flex items-center justify-between h-12 px-3">
        {/* 左侧: 汉堡菜单 */}
        <Button
          variant="ghost"
          size="icon"
          className="min-w-[44px] min-h-[44px] touch-manipulation"
          onClick={onMenuToggle}
          aria-label="打开菜单"
        >
          <Menu className="w-5 h-5" />
        </Button>

        {/* 中间: 标题 */}
        <h1 className="text-base font-semibold truncate max-w-[50vw] text-center">
          {title}
        </h1>

        {/* 右侧: 搜索 + 通知 */}
        <div className="flex items-center gap-0.5">
          {showSearch && (
            <Button
              variant="ghost"
              size="icon"
              className="min-w-[44px] min-h-[44px] touch-manipulation"
              onClick={onSearchClick}
              aria-label="搜索"
            >
              <Search className="w-5 h-5" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="min-w-[44px] min-h-[44px] touch-manipulation relative"
            onClick={onNotificationClick}
            aria-label="通知"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span
                className={cn(
                  'absolute top-1.5 right-1.5 min-w-[16px] h-4',
                  'flex items-center justify-center',
                  'rounded-full bg-destructive text-destructive-foreground',
                  'text-[10px] font-medium px-1 leading-none'
                )}
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </Button>
        </div>
      </div>
    </header>
  );
}
