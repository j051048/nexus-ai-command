/**
 * 下拉刷新指示器组件
 * 搭配 usePullToRefresh hook 使用
 */

import React from 'react';
import { Loader2, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PullToRefreshIndicatorProps {
  pullDistance: number;
  isRefreshing: boolean;
  threshold?: number;
}

export function PullToRefreshIndicator({
  pullDistance,
  isRefreshing,
  threshold = 80,
}: PullToRefreshIndicatorProps) {
  if (pullDistance <= 0 && !isRefreshing) return null;

  const progress = Math.min(pullDistance / threshold, 1);
  const reachedThreshold = progress >= 1;

  return (
    <div
      className="flex items-center justify-center overflow-hidden transition-all"
      style={{ height: pullDistance > 0 ? `${pullDistance}px` : isRefreshing ? '40px' : '0px' }}
    >
      <div
        className={cn(
          'flex items-center gap-2 text-sm text-muted-foreground',
          reachedThreshold && !isRefreshing && 'text-primary'
        )}
      >
        {isRefreshing ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>刷新中...</span>
          </>
        ) : (
          <>
            <ArrowDown
              className={cn(
                'w-4 h-4 transition-transform duration-200',
                reachedThreshold && 'rotate-180'
              )}
            />
            <span>{reachedThreshold ? '释放刷新' : '下拉刷新'}</span>
          </>
        )}
      </div>
    </div>
  );
}
