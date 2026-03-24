/**
 * 移动端页面顶部导航栏
 * 显示标题、返回按钮、右侧操作（搜索/AI）
 */

import React from 'react';
import { ArrowLeft, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface MobilePageHeaderProps {
  /** 页面标题 */
  title: string;
  /** 是否显示返回按钮 */
  showBack?: boolean;
  /** 返回按钮回调 */
  onBack?: () => void;
  /** AI 按钮回调 */
  onAIPress?: () => void;
  /** 搜索按钮回调 */
  onSearch?: () => void;
  /** 自定义右侧操作 */
  rightActions?: React.ReactNode;
  /** 额外的 className */
  className?: string;
}

export default function MobilePageHeader({
  title,
  showBack = false,
  onBack,
  onAIPress,
  onSearch,
  rightActions,
  className,
}: MobilePageHeaderProps) {
  return (
    <header
      className={cn(
        'h-12 flex items-center justify-between px-2 border-b border-border bg-background/95 backdrop-blur-sm',
        'pt-[env(safe-area-inset-top)]',
        'flex-shrink-0',
        'mobile-header',
        className
      )}
    >
      {/* 左侧：返回按钮 + 标题 */}
      <div className="flex items-center gap-1 flex-1 min-w-0">
        {showBack && (
          <Button
            variant="ghost"
            size="sm"
            className="h-10 w-10 p-0 flex-shrink-0 touch-manipulation"
            onClick={onBack}
            aria-label="返回"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
        )}
        <h1 className="text-base font-semibold text-foreground truncate">
          {title}
        </h1>
      </div>

      {/* 右侧：操作按钮 */}
      <div className="flex items-center gap-0.5 flex-shrink-0">
        {rightActions}
        {onSearch && (
          <Button
            variant="ghost"
            size="sm"
            className="h-10 w-10 p-0 touch-manipulation"
            onClick={onSearch}
            aria-label="搜索"
          >
            <Search className="w-4.5 h-4.5" />
          </Button>
        )}
        {onAIPress && (
          <Button
            variant="ghost"
            size="sm"
            className="h-10 w-10 p-0 touch-manipulation"
            onClick={onAIPress}
            aria-label="AI 助手"
          >
            <Sparkles className="w-4.5 h-4.5 text-primary" />
          </Button>
        )}
      </div>
    </header>
  );
}
