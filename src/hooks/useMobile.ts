import { useState, useEffect, useCallback, useRef, RefObject } from 'react';

const MOBILE_BREAKPOINT = 768;
const TABLET_BREAKPOINT = 1024;

/**
 * 移动端检测 Hook
 * 返回当前设备类型和屏幕宽度
 */
export function useMobile() {
  const [screenWidth, setScreenWidth] = useState(window.innerWidth);

  useEffect(() => {
    let rafId: number;
    const handleResize = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        setScreenWidth(window.innerWidth);
      });
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(rafId);
    };
  }, []);

  return {
    isMobile: screenWidth < MOBILE_BREAKPOINT,
    isTablet: screenWidth >= MOBILE_BREAKPOINT && screenWidth < TABLET_BREAKPOINT,
    screenWidth,
  };
}

interface SwipeOptions {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  threshold?: number;
}

/**
 * 滑动手势 Hook
 * 为指定元素添加左右滑动检测
 */
export function useSwipe(
  ref: RefObject<HTMLElement | null>,
  { onSwipeLeft, onSwipeRight, threshold = 50 }: SwipeOptions
) {
  const startX = useRef(0);
  const startY = useRef(0);
  const isDragging = useRef(false);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    startX.current = e.touches[0].clientX;
    startY.current = e.touches[0].clientY;
    isDragging.current = true;
  }, []);

  const handleTouchEnd = useCallback(
    (e: TouchEvent) => {
      if (!isDragging.current) return;
      isDragging.current = false;

      const endX = e.changedTouches[0].clientX;
      const endY = e.changedTouches[0].clientY;
      const diffX = endX - startX.current;
      const diffY = endY - startY.current;

      // 确保水平滑动幅度大于垂直滑动（避免误判滚动）
      if (Math.abs(diffX) < threshold || Math.abs(diffX) < Math.abs(diffY)) {
        return;
      }

      if (diffX < -threshold && onSwipeLeft) {
        onSwipeLeft();
      } else if (diffX > threshold && onSwipeRight) {
        onSwipeRight();
      }
    },
    [onSwipeLeft, onSwipeRight, threshold]
  );

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    el.addEventListener('touchstart', handleTouchStart, { passive: true });
    el.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      el.removeEventListener('touchstart', handleTouchStart);
      el.removeEventListener('touchend', handleTouchEnd);
    };
  }, [ref, handleTouchStart, handleTouchEnd]);
}
