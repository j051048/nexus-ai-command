/**
 * 移动端下拉刷新 Hook
 * 轻量级实现，不依赖第三方库
 */

import { useState, useCallback, useRef, useEffect } from 'react';

interface UsePullToRefreshOptions {
  /** 触发刷新的下拉距离阈值 (px) */
  threshold?: number;
  /** 刷新回调 */
  onRefresh: () => Promise<void>;
  /** 是否启用 */
  enabled?: boolean;
}

interface UsePullToRefreshReturn {
  /** 是否正在刷新 */
  isRefreshing: boolean;
  /** 当前下拉距离 (用于UI反馈) */
  pullDistance: number;
  /** 绑定到滚动容器的 ref */
  containerRef: React.RefObject<HTMLDivElement>;
  /** 绑定到容器的事件处理器 */
  handlers: {
    onTouchStart: (e: React.TouchEvent) => void;
    onTouchMove: (e: React.TouchEvent) => void;
    onTouchEnd: () => void;
  };
}

export function usePullToRefresh({
  threshold = 80,
  onRefresh,
  enabled = true,
}: UsePullToRefreshOptions): UsePullToRefreshReturn {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null!);
  const startY = useRef(0);
  const isPulling = useRef(false);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (!enabled || isRefreshing) return;
      const container = containerRef.current;
      if (container && container.scrollTop <= 0) {
        startY.current = e.touches[0].clientY;
        isPulling.current = true;
      }
    },
    [enabled, isRefreshing]
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!isPulling.current || !enabled || isRefreshing) return;
      const delta = e.touches[0].clientY - startY.current;
      if (delta > 0) {
        // 阻尼效果: 实际距离 = delta * 0.4
        setPullDistance(Math.min(delta * 0.4, threshold * 1.5));
      }
    },
    [enabled, isRefreshing, threshold]
  );

  const onTouchEnd = useCallback(async () => {
    if (!isPulling.current) return;
    isPulling.current = false;

    if (pullDistance >= threshold && !isRefreshing) {
      setIsRefreshing(true);
      setPullDistance(threshold * 0.5); // 保持小幅度指示器
      try {
        await onRefresh();
      } finally {
        setIsRefreshing(false);
        setPullDistance(0);
      }
    } else {
      setPullDistance(0);
    }
  }, [pullDistance, threshold, isRefreshing, onRefresh]);

  // 清理
  useEffect(() => {
    return () => {
      isPulling.current = false;
    };
  }, []);

  return {
    isRefreshing,
    pullDistance,
    containerRef,
    handlers: {
      onTouchStart,
      onTouchMove,
      onTouchEnd,
    },
  };
}
