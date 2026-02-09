/**
 * P0 UX Enhancement: Animation utilities and presets
 * 提供统一的动画配置和工具函数
 */

import { useEffect, useState, useRef } from 'react';

// ==================== 动画配置预设 ====================

/**
 * 页面过渡动画配置 (用于 Framer Motion)
 */
export const pageTransition = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
  transition: { duration: 0.3, ease: 'easeOut' },
};

/**
 * 淡入上移动画
 */
export const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: 'easeOut' },
};

/**
 * 淡入下移动画
 */
export const fadeInDown = {
  initial: { opacity: 0, y: -20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4, ease: 'easeOut' },
};

/**
 * 淡入缩放动画
 */
export const fadeInScale = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.2, ease: 'easeOut' },
};

/**
 * 滑入动画 (从左)
 */
export const slideInLeft = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
  transition: { duration: 0.3, ease: 'easeOut' },
};

/**
 * 滑入动画 (从右)
 */
export const slideInRight = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 20 },
  transition: { duration: 0.3, ease: 'easeOut' },
};

/**
 * 交错容器动画配置
 */
export const staggerContainer = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
};

/**
 * 交错子元素动画配置
 */
export const staggerItem = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

// ==================== CSS 动画类名 ====================

/**
 * 获取进入动画类名
 */
export function getEnterAnimationClass(
  type: 'fade' | 'slide-up' | 'slide-down' | 'scale' | 'slide-left' | 'slide-right' = 'fade',
  duration: 'fast' | 'normal' | 'slow' = 'normal'
): string {
  const durationClass = {
    fast: 'duration-150',
    normal: 'duration-300',
    slow: 'duration-500',
  }[duration];

  const animationClass = {
    fade: 'animate-in fade-in',
    'slide-up': 'animate-in fade-in slide-in-from-bottom-4',
    'slide-down': 'animate-in fade-in slide-in-from-top-4',
    scale: 'animate-in fade-in zoom-in-95',
    'slide-left': 'animate-in fade-in slide-in-from-left-4',
    'slide-right': 'animate-in fade-in slide-in-from-right-4',
  }[type];

  return `${animationClass} ${durationClass}`;
}

// ==================== React Hooks ====================

/**
 * 数字递增动画 Hook
 * @param end 目标数值
 * @param duration 动画持续时间 (ms)
 * @param startOnMount 是否在挂载时开始
 */
export function useCountUp(
  end: number,
  duration: number = 1000,
  startOnMount: boolean = true
): [number, () => void] {
  const [count, setCount] = useState(0);
  const animationRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  const startAnimation = () => {
    startTimeRef.current = null;
    setCount(0);

    const animate = (timestamp: number) => {
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }

      const progress = Math.min((timestamp - startTimeRef.current) / duration, 1);
      // 使用 easeOutQuart 缓动函数
      const easedProgress = 1 - Math.pow(1 - progress, 4);
      setCount(Math.floor(easedProgress * end));

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setCount(end);
      }
    };

    animationRef.current = requestAnimationFrame(animate);
  };

  useEffect(() => {
    if (startOnMount) {
      startAnimation();
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [end, duration, startOnMount]);

  return [count, startAnimation];
}

/**
 * 延迟显示 Hook (用于避免闪烁)
 * @param delay 延迟时间 (ms)
 */
export function useDelayedShow(delay: number = 200): boolean {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  return show;
}

/**
 * 交错动画延迟计算
 * @param index 元素索引
 * @param baseDelay 基础延迟 (ms)
 * @param increment 每个元素增加的延迟 (ms)
 */
export function getStaggerDelay(index: number, baseDelay: number = 0, increment: number = 50): number {
  return baseDelay + index * increment;
}

/**
 * 生成交错动画样式
 */
export function getStaggerStyle(index: number, baseDelay: number = 0, increment: number = 50) {
  return {
    animationDelay: `${getStaggerDelay(index, baseDelay, increment)}ms`,
    animationFillMode: 'backwards' as const,
  };
}

/**
 * 视口进入检测 Hook
 * @param threshold 触发阈值 (0-1)
 */
export function useInView(
  threshold: number = 0.1
): [React.RefObject<HTMLDivElement>, boolean] {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, inView];
}

/**
 * 打字机效果 Hook
 * @param text 要显示的文本
 * @param speed 打字速度 (ms/字符)
 */
export function useTypewriter(text: string, speed: number = 50): string {
  const [displayText, setDisplayText] = useState('');

  useEffect(() => {
    setDisplayText('');
    let index = 0;

    const interval = setInterval(() => {
      if (index < text.length) {
        setDisplayText(text.slice(0, index + 1));
        index++;
      } else {
        clearInterval(interval);
      }
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed]);

  return displayText;
}

/**
 * 脉冲动画 Hook (用于提示用户注意)
 */
export function usePulse(duration: number = 2000): [boolean, () => void] {
  const [isPulsing, setIsPulsing] = useState(false);

  const triggerPulse = () => {
    setIsPulsing(true);
    setTimeout(() => setIsPulsing(false), duration);
  };

  return [isPulsing, triggerPulse];
}

export default {
  pageTransition,
  fadeInUp,
  fadeInDown,
  fadeInScale,
  slideInLeft,
  slideInRight,
  staggerContainer,
  staggerItem,
  getEnterAnimationClass,
  useCountUp,
  useDelayedShow,
  getStaggerDelay,
  getStaggerStyle,
  useInView,
  useTypewriter,
  usePulse,
};