/**
 * P0 UX Enhancement: Animation utilities and presets
 * 提供统一的动画配置和工具函数
 * 
 * 功能包括：
 * - Framer Motion 动画预设
 * - CSS 动画类名生成器
 * - 性能优化的 React Hooks
 * - 高级动画效果（弹簧、手势、滚动联动）
 * - 无障碍支持（减弱动画偏好）
 */

import { useEffect, useState, useRef, useCallback, useMemo } from 'react';

// ==================== 缓动函数预设 ====================

/**
 * 常用缓动函数 (CSS cubic-bezier)
 */
export const easings = {
  // 标准缓动
  linear: [0, 0, 1, 1] as const,
  easeIn: [0.4, 0, 1, 1] as const,
  easeOut: [0, 0, 0.2, 1] as const,
  easeInOut: [0.4, 0, 0.2, 1] as const,
  
  // 高级缓动
  easeInQuad: [0.55, 0.085, 0.68, 0.53] as const,
  easeOutQuad: [0.25, 0.46, 0.45, 0.94] as const,
  easeInOutQuad: [0.455, 0.03, 0.515, 0.955] as const,
  
  easeInCubic: [0.55, 0.055, 0.675, 0.19] as const,
  easeOutCubic: [0.215, 0.61, 0.355, 1] as const,
  easeInOutCubic: [0.645, 0.045, 0.355, 1] as const,
  
  easeInQuart: [0.895, 0.03, 0.685, 0.22] as const,
  easeOutQuart: [0.165, 0.84, 0.44, 1] as const,
  easeInOutQuart: [0.77, 0, 0.175, 1] as const,
  
  // 弹性效果
  easeOutBack: [0.175, 0.885, 0.32, 1.275] as const,
  easeInBack: [0.6, -0.28, 0.735, 0.045] as const,
  easeInOutBack: [0.68, -0.55, 0.265, 1.55] as const,
  
  // 弹跳效果
  bounce: [0.68, -0.6, 0.32, 1.6] as const,
} as const;

/**
 * 弹簧动画配置预设
 */
export const springPresets = {
  // 轻柔弹簧 - 适合小元素
  gentle: { type: 'spring' as const, stiffness: 120, damping: 14, mass: 1 },
  // 默认弹簧 - 平衡效果
  default: { type: 'spring' as const, stiffness: 170, damping: 26, mass: 1 },
  // 有弹性 - 适合按钮、卡片
  bouncy: { type: 'spring' as const, stiffness: 400, damping: 10, mass: 1 },
  // 快速响应 - 适合快速反馈
  snappy: { type: 'spring' as const, stiffness: 500, damping: 30, mass: 1 },
  // 缓慢弹簧 - 适合大元素
  slow: { type: 'spring' as const, stiffness: 80, damping: 20, mass: 1 },
  // 刚性 - 几乎无弹性
  stiff: { type: 'spring' as const, stiffness: 700, damping: 50, mass: 1 },
} as const;

// ==================== Framer Motion 动画预设 ====================

/**
 * 页面过渡动画配置 (用于 Framer Motion)
 */
export const pageTransition = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
  transition: { duration: 0.3, ease: easings.easeOut },
};

/**
 * 淡入上移动画
 */
export const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
  transition: { duration: 0.4, ease: easings.easeOut },
};

/**
 * 淡入下移动画
 */
export const fadeInDown = {
  initial: { opacity: 0, y: -20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
  transition: { duration: 0.4, ease: easings.easeOut },
};

/**
 * 淡入缩放动画
 */
export const fadeInScale = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.2, ease: easings.easeOut },
};

/**
 * 滑入动画 (从左)
 */
export const slideInLeft = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
  transition: { duration: 0.3, ease: easings.easeOut },
};

/**
 * 滑入动画 (从右)
 */
export const slideInRight = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 20 },
  transition: { duration: 0.3, ease: easings.easeOut },
};

/**
 * 弹出动画 (适合模态框、下拉菜单)
 */
export const popIn = {
  initial: { opacity: 0, scale: 0.9, y: -10 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.9, y: -10 },
  transition: springPresets.bouncy,
};

/**
 * 弹性缩放动画 (适合按钮点击)
 */
export const springScale = {
  initial: { scale: 1 },
  tap: { scale: 0.95 },
  hover: { scale: 1.02 },
  transition: springPresets.snappy,
};

/**
 * 翻转动画 (适合卡片翻转)
 */
export const flipIn = {
  initial: { opacity: 0, rotateY: -90 },
  animate: { opacity: 1, rotateY: 0 },
  exit: { opacity: 0, rotateY: 90 },
  transition: { duration: 0.5, ease: easings.easeOutCubic },
};

/**
 * 模糊淡入动画
 */
export const blurFadeIn = {
  initial: { opacity: 0, filter: 'blur(10px)' },
  animate: { opacity: 1, filter: 'blur(0px)' },
  exit: { opacity: 0, filter: 'blur(10px)' },
  transition: { duration: 0.4, ease: easings.easeOut },
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
 * 快速交错容器
 */
export const staggerContainerFast = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.05,
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

/**
 * 交错子元素 - 水平滑入
 */
export const staggerItemHorizontal = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0 },
};

/**
 * 交错子元素 - 缩放
 */
export const staggerItemScale = {
  initial: { opacity: 0, scale: 0.8 },
  animate: { opacity: 1, scale: 1 },
};

/**
 * 列表项动画 (带弹簧)
 */
export const listItemSpring = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 20, transition: { duration: 0.2 } },
  transition: springPresets.gentle,
};

/**
 * 卡片悬浮动画
 */
export const cardHover = {
  rest: { scale: 1, y: 0, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' },
  hover: { 
    scale: 1.02, 
    y: -4, 
    boxShadow: '0 10px 40px rgba(0,0,0,0.15)',
    transition: springPresets.gentle,
  },
};

/**
 * 抖动动画 (用于错误提示)
 */
export const shake = {
  initial: { x: 0 },
  animate: {
    x: [0, -10, 10, -10, 10, -5, 5, 0],
    transition: { duration: 0.5 },
  },
};

/**
 * 脉冲动画
 */
export const pulse = {
  initial: { scale: 1 },
  animate: {
    scale: [1, 1.05, 1],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
};

/**
 * 呼吸效果 (适合加载状态)
 */
export const breathe = {
  initial: { opacity: 0.5 },
  animate: {
    opacity: [0.5, 1, 0.5],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
};

// ==================== CSS 动画类名 ====================

export type AnimationType = 
  | 'fade' 
  | 'slide-up' 
  | 'slide-down' 
  | 'scale' 
  | 'slide-left' 
  | 'slide-right'
  | 'bounce'
  | 'spin';

export type AnimationDuration = 'fastest' | 'fast' | 'normal' | 'slow' | 'slowest';

/**
 * 获取进入动画类名
 */
export function getEnterAnimationClass(
  type: AnimationType = 'fade',
  duration: AnimationDuration = 'normal'
): string {
  const durationClass = {
    fastest: 'duration-75',
    fast: 'duration-150',
    normal: 'duration-300',
    slow: 'duration-500',
    slowest: 'duration-700',
  }[duration];

  const animationClass = {
    fade: 'animate-in fade-in',
    'slide-up': 'animate-in fade-in slide-in-from-bottom-4',
    'slide-down': 'animate-in fade-in slide-in-from-top-4',
    scale: 'animate-in fade-in zoom-in-95',
    'slide-left': 'animate-in fade-in slide-in-from-left-4',
    'slide-right': 'animate-in fade-in slide-in-from-right-4',
    bounce: 'animate-bounce',
    spin: 'animate-spin',
  }[type];

  return `${animationClass} ${durationClass}`;
}

/**
 * 获取退出动画类名
 */
export function getExitAnimationClass(
  type: AnimationType = 'fade',
  duration: AnimationDuration = 'normal'
): string {
  const durationClass = {
    fastest: 'duration-75',
    fast: 'duration-150',
    normal: 'duration-300',
    slow: 'duration-500',
    slowest: 'duration-700',
  }[duration];

  const animationClass = {
    fade: 'animate-out fade-out',
    'slide-up': 'animate-out fade-out slide-out-to-top-4',
    'slide-down': 'animate-out fade-out slide-out-to-bottom-4',
    scale: 'animate-out fade-out zoom-out-95',
    'slide-left': 'animate-out fade-out slide-out-to-left-4',
    'slide-right': 'animate-out fade-out slide-out-to-right-4',
    bounce: 'animate-out fade-out',
    spin: 'animate-out fade-out',
  }[type];

  return `${animationClass} ${durationClass}`;
}

/**
 * 生成悬浮效果类名
 */
export function getHoverAnimationClass(
  effect: 'lift' | 'glow' | 'scale' | 'brightness' = 'lift'
): string {
  const effectClasses = {
    lift: 'transition-all hover:-translate-y-1 hover:shadow-lg',
    glow: 'transition-all hover:shadow-lg hover:shadow-primary/25',
    scale: 'transition-transform hover:scale-105',
    brightness: 'transition-all hover:brightness-110',
  };
  return effectClasses[effect];
}

/**
 * 生成过渡类名
 */
export function getTransitionClass(
  property: 'all' | 'colors' | 'opacity' | 'transform' | 'shadow' = 'all',
  duration: AnimationDuration = 'normal'
): string {
  const durationClass = {
    fastest: 'duration-75',
    fast: 'duration-150',
    normal: 'duration-300',
    slow: 'duration-500',
    slowest: 'duration-700',
  }[duration];

  const propertyClass = {
    all: 'transition-all',
    colors: 'transition-colors',
    opacity: 'transition-opacity',
    transform: 'transition-transform',
    shadow: 'transition-shadow',
  }[property];

  return `${propertyClass} ${durationClass} ease-out`;
}

// ==================== React Hooks ====================

/**
 * 检测用户是否偏好减弱动画
 */
export function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return prefersReducedMotion;
}

/**
 * 数字递增动画 Hook
 * @param end 目标数值
 * @param duration 动画持续时间 (ms)
 * @param options 配置选项
 */
export function useCountUp(
  end: number,
  duration: number = 1000,
  options: {
    startOnMount?: boolean;
    startFrom?: number;
    decimals?: number;
    easing?: 'linear' | 'easeOut' | 'easeInOut' | 'easeOutQuart';
  } = {}
): [number, () => void, () => void] {
  const { startOnMount = true, startFrom = 0, decimals = 0, easing = 'easeOutQuart' } = options;
  const [count, setCount] = useState(startFrom);
  const animationRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  // 缓动函数
  const easingFunctions = useMemo(() => ({
    linear: (t: number) => t,
    easeOut: (t: number) => 1 - Math.pow(1 - t, 3),
    easeInOut: (t: number) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
    easeOutQuart: (t: number) => 1 - Math.pow(1 - t, 4),
  }), []);

  const startAnimation = useCallback(() => {
    if (prefersReducedMotion) {
      setCount(end);
      return;
    }

    startTimeRef.current = null;
    setCount(startFrom);

    const animate = (timestamp: number) => {
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp;
      }

      const progress = Math.min((timestamp - startTimeRef.current) / duration, 1);
      const easedProgress = easingFunctions[easing](progress);
      const currentValue = startFrom + (end - startFrom) * easedProgress;
      
      setCount(decimals > 0 ? Number(currentValue.toFixed(decimals)) : Math.floor(currentValue));

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setCount(end);
      }
    };

    animationRef.current = requestAnimationFrame(animate);
  }, [end, duration, startFrom, decimals, easing, prefersReducedMotion, easingFunctions]);

  const reset = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    setCount(startFrom);
  }, [startFrom]);

  useEffect(() => {
    if (startOnMount) {
      startAnimation();
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [end, duration, startOnMount, startAnimation]);

  return [count, startAnimation, reset];
}

/**
 * 延迟显示 Hook (用于避免闪烁)
 * @param delay 延迟时间 (ms)
 * @param condition 可选条件，只有满足时才开始计时
 */
export function useDelayedShow(delay: number = 200, condition: boolean = true): boolean {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!condition) {
      setShow(false);
      return;
    }
    
    const timer = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(timer);
  }, [delay, condition]);

  return show;
}

/**
 * 延迟隐藏 Hook (用于退出动画)
 * @param isVisible 是否可见
 * @param delay 延迟时间 (ms)
 */
export function useDelayedHide(isVisible: boolean, delay: number = 300): boolean {
  const [shouldRender, setShouldRender] = useState(isVisible);

  useEffect(() => {
    if (isVisible) {
      setShouldRender(true);
    } else {
      const timer = setTimeout(() => setShouldRender(false), delay);
      return () => clearTimeout(timer);
    }
  }, [isVisible, delay]);

  return shouldRender;
}

/**
 * 交错动画延迟计算
 * @param index 元素索引
 * @param baseDelay 基础延迟 (ms)
 * @param increment 每个元素增加的延迟 (ms)
 * @param maxDelay 最大延迟限制 (ms)
 */
export function getStaggerDelay(
  index: number, 
  baseDelay: number = 0, 
  increment: number = 50,
  maxDelay?: number
): number {
  const delay = baseDelay + index * increment;
  return maxDelay ? Math.min(delay, maxDelay) : delay;
}

/**
 * 生成交错动画样式
 */
export function getStaggerStyle(
  index: number, 
  baseDelay: number = 0, 
  increment: number = 50,
  maxDelay?: number
): React.CSSProperties {
  return {
    animationDelay: `${getStaggerDelay(index, baseDelay, increment, maxDelay)}ms`,
    animationFillMode: 'backwards',
  };
}

/**
 * 交错动画 Framer Motion variants 生成器
 */
export function createStaggerVariants(
  staggerDelay: number = 0.1,
  initialDelay: number = 0,
  options?: {
    direction?: 'up' | 'down' | 'left' | 'right';
    distance?: number;
    scale?: number;
  }
) {
  const { direction = 'up', distance = 20, scale } = options || {};
  
  const getInitialPosition = () => {
    switch (direction) {
      case 'up': return { y: distance };
      case 'down': return { y: -distance };
      case 'left': return { x: distance };
      case 'right': return { x: -distance };
    }
  };

  return {
    container: {
      initial: {},
      animate: {
        transition: {
          staggerChildren: staggerDelay,
          delayChildren: initialDelay,
        },
      },
      exit: {
        transition: {
          staggerChildren: staggerDelay / 2,
          staggerDirection: -1,
        },
      },
    },
    item: {
      initial: { 
        opacity: 0, 
        ...getInitialPosition(),
        ...(scale ? { scale } : {}),
      },
      animate: { 
        opacity: 1, 
        x: 0, 
        y: 0, 
        scale: 1,
        transition: springPresets.gentle,
      },
      exit: { 
        opacity: 0, 
        ...getInitialPosition(),
        transition: { duration: 0.2 },
      },
    },
  };
}

/**
 * 视口进入检测 Hook
 * @param options 配置选项
 */
export function useInView(options: {
  threshold?: number;
  rootMargin?: string;
  triggerOnce?: boolean;
  onChange?: (inView: boolean) => void;
} = {}): [React.RefObject<HTMLDivElement>, boolean] {
  const { threshold = 0.1, rootMargin = '0px', triggerOnce = true, onChange } = options;
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        const isIntersecting = entry.isIntersecting;
        setInView(isIntersecting);
        onChange?.(isIntersecting);
        
        if (isIntersecting && triggerOnce) {
          observer.disconnect();
        }
      },
      { threshold, rootMargin }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [threshold, rootMargin, triggerOnce, onChange]);

  return [ref, inView];
}

/**
 * 滚动进度 Hook
 * @param options 配置选项
 */
export function useScrollProgress(options: {
  target?: React.RefObject<HTMLElement>;
  offset?: [string, string];
} = {}): number {
  const { target, offset = ['start end', 'end start'] } = options;
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const element = target?.current || document.documentElement;
    
    const handleScroll = () => {
      const scrollTop = target?.current 
        ? target.current.scrollTop 
        : window.scrollY;
      const scrollHeight = target?.current
        ? target.current.scrollHeight - target.current.clientHeight
        : document.documentElement.scrollHeight - window.innerHeight;
      
      const currentProgress = scrollHeight > 0 ? scrollTop / scrollHeight : 0;
      setProgress(Math.min(Math.max(currentProgress, 0), 1));
    };

    const targetElement = target?.current || window;
    targetElement.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => targetElement.removeEventListener('scroll', handleScroll);
  }, [target]);

  return progress;
}

/**
 * 视差滚动 Hook
 * @param speed 视差速度 (-1 到 1，负值反向)
 */
export function useParallax(speed: number = 0.5): number {
  const [offset, setOffset] = useState(0);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (prefersReducedMotion) return;

    const handleScroll = () => {
      setOffset(window.scrollY * speed);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [speed, prefersReducedMotion]);

  return prefersReducedMotion ? 0 : offset;
}

/**
 * 打字机效果 Hook
 * @param text 要显示的文本
 * @param options 配置选项
 */
export function useTypewriter(
  text: string, 
  options: {
    speed?: number;
    delay?: number;
    cursor?: boolean;
    onComplete?: () => void;
  } = {}
): { displayText: string; isTyping: boolean; reset: () => void } {
  const { speed = 50, delay = 0, cursor = false, onComplete } = options;
  const [displayText, setDisplayText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const prefersReducedMotion = usePrefersReducedMotion();

  const reset = useCallback(() => {
    setDisplayText('');
    setIsTyping(false);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) {
      setDisplayText(text);
      onComplete?.();
      return;
    }

    setDisplayText('');
    setIsTyping(true);
    let index = 0;
    let timeoutId: NodeJS.Timeout;

    const startTyping = () => {
      const interval = setInterval(() => {
        if (index < text.length) {
          setDisplayText(text.slice(0, index + 1));
          index++;
        } else {
          clearInterval(interval);
          setIsTyping(false);
          onComplete?.();
        }
      }, speed);

      return () => clearInterval(interval);
    };

    if (delay > 0) {
      timeoutId = setTimeout(startTyping, delay);
      return () => clearTimeout(timeoutId);
    } else {
      return startTyping();
    }
  }, [text, speed, delay, prefersReducedMotion, onComplete]);

  return { 
    displayText: cursor && isTyping ? displayText + '|' : displayText, 
    isTyping, 
    reset 
  };
}

/**
 * 脉冲动画 Hook (用于提示用户注意)
 */
export function usePulse(duration: number = 2000): [boolean, () => void, () => void] {
  const [isPulsing, setIsPulsing] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const triggerPulse = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setIsPulsing(true);
    timerRef.current = setTimeout(() => setIsPulsing(false), duration);
  }, [duration]);

  const stopPulse = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setIsPulsing(false);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  return [isPulsing, triggerPulse, stopPulse];
}

/**
 * 动画状态 Hook (用于复杂动画序列)
 */
export function useAnimationState<T extends string>(
  states: T[],
  options: {
    initialState?: T;
    autoAdvance?: boolean;
    interval?: number;
    loop?: boolean;
  } = {}
): {
  currentState: T;
  stateIndex: number;
  next: () => void;
  prev: () => void;
  goTo: (state: T) => void;
  reset: () => void;
} {
  const { initialState, autoAdvance = false, interval = 1000, loop = true } = options;
  const [stateIndex, setStateIndex] = useState(
    initialState ? states.indexOf(initialState) : 0
  );

  const next = useCallback(() => {
    setStateIndex((prev) => {
      const nextIndex = prev + 1;
      if (nextIndex >= states.length) {
        return loop ? 0 : prev;
      }
      return nextIndex;
    });
  }, [states.length, loop]);

  const prev = useCallback(() => {
    setStateIndex((prev) => {
      const nextIndex = prev - 1;
      if (nextIndex < 0) {
        return loop ? states.length - 1 : 0;
      }
      return nextIndex;
    });
  }, [states.length, loop]);

  const goTo = useCallback((state: T) => {
    const index = states.indexOf(state);
    if (index !== -1) {
      setStateIndex(index);
    }
  }, [states]);

  const reset = useCallback(() => {
    setStateIndex(initialState ? states.indexOf(initialState) : 0);
  }, [states, initialState]);

  useEffect(() => {
    if (!autoAdvance) return;

    const timer = setInterval(next, interval);
    return () => clearInterval(timer);
  }, [autoAdvance, interval, next]);

  return {
    currentState: states[stateIndex],
    stateIndex,
    next,
    prev,
    goTo,
    reset,
  };
}

/**
 * 弹簧值 Hook (用于平滑数值过渡)
 */
export function useSpringValue(
  targetValue: number,
  config: {
    stiffness?: number;
    damping?: number;
    mass?: number;
    precision?: number;
  } = {}
): number {
  const { stiffness = 170, damping = 26, mass = 1, precision = 0.01 } = config;
  const [value, setValue] = useState(targetValue);
  const velocityRef = useRef(0);
  const animationRef = useRef<number | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (prefersReducedMotion) {
      setValue(targetValue);
      return;
    }

    let lastTime = performance.now();

    const animate = (currentTime: number) => {
      const deltaTime = Math.min((currentTime - lastTime) / 1000, 0.064); // 限制最大帧时间
      lastTime = currentTime;

      const displacement = value - targetValue;
      const springForce = -stiffness * displacement;
      const dampingForce = -damping * velocityRef.current;
      const acceleration = (springForce + dampingForce) / mass;

      velocityRef.current += acceleration * deltaTime;
      const newValue = value + velocityRef.current * deltaTime;

      // 检查是否足够接近目标值
      if (
        Math.abs(newValue - targetValue) < precision &&
        Math.abs(velocityRef.current) < precision
      ) {
        setValue(targetValue);
        velocityRef.current = 0;
        return;
      }

      setValue(newValue);
      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [targetValue, stiffness, damping, mass, precision, prefersReducedMotion, value]);

  return prefersReducedMotion ? targetValue : value;
}

/**
 * 鼠标跟随 Hook
 */
export function useMousePosition(options: {
  smoothing?: number;
  targetRef?: React.RefObject<HTMLElement>;
} = {}): { x: number; y: number; isInside: boolean } {
  const { smoothing = 0.1, targetRef } = options;
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isInside, setIsInside] = useState(false);
  const targetPosition = useRef({ x: 0, y: 0 });
  const animationRef = useRef<number | null>(null);
  const prefersReducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (prefersReducedMotion) return;

    const element = targetRef?.current || document;
    const currentTarget = targetRef?.current;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = currentTarget?.getBoundingClientRect();
      targetPosition.current = {
        x: rect ? e.clientX - rect.left : e.clientX,
        y: rect ? e.clientY - rect.top : e.clientY,
      };
    };

    const handleMouseEnter = () => setIsInside(true);
    const handleMouseLeave = () => setIsInside(false);

    const animate = () => {
      setPosition((prev) => ({
        x: prev.x + (targetPosition.current.x - prev.x) * smoothing,
        y: prev.y + (targetPosition.current.y - prev.y) * smoothing,
      }));
      animationRef.current = requestAnimationFrame(animate);
    };

    element.addEventListener('mousemove', handleMouseMove as EventListener);
    if (currentTarget) {
      currentTarget.addEventListener('mouseenter', handleMouseEnter);
      currentTarget.addEventListener('mouseleave', handleMouseLeave);
    }
    animationRef.current = requestAnimationFrame(animate);

    return () => {
      element.removeEventListener('mousemove', handleMouseMove as EventListener);
      if (currentTarget) {
        currentTarget.removeEventListener('mouseenter', handleMouseEnter);
        currentTarget.removeEventListener('mouseleave', handleMouseLeave);
      }
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [smoothing, targetRef, prefersReducedMotion]);

  return { ...position, isInside };
}

// ==================== 动画工具函数 ====================

/**
 * 将动画持续时间转换为毫秒
 */
export function durationToMs(duration: AnimationDuration): number {
  const durations: Record<AnimationDuration, number> = {
    fastest: 75,
    fast: 150,
    normal: 300,
    slow: 500,
    slowest: 700,
  };
  return durations[duration];
}

/**
 * 获取安全的动画配置 (考虑减弱动画偏好)
 */
export function getSafeAnimationConfig<T extends object>(
  config: T,
  reducedConfig?: Partial<T>
): T {
  if (typeof window === 'undefined') return config;
  
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (prefersReducedMotion && reducedConfig) {
    return { ...config, ...reducedConfig };
  }
  
  if (prefersReducedMotion) {
    // 返回无动画的配置
    return {
      ...config,
      initial: undefined,
      animate: undefined,
      exit: undefined,
      transition: { duration: 0 },
    } as T;
  }
  
  return config;
}

/**
 * 创建循环动画配置
 */
export function createLoopAnimation(
  keyframes: Record<string, number[]>,
  duration: number = 2,
  ease: string = 'easeInOut'
) {
  return {
    animate: keyframes,
    transition: {
      duration,
      ease,
      repeat: Infinity,
      repeatType: 'reverse' as const,
    },
  };
}

/**
 * 创建序列动画配置
 */
export function createSequenceAnimation(
  steps: Array<{
    animate: Record<string, number | string>;
    duration?: number;
  }>
) {
  const keyframes: Record<string, (number | string)[]> = {};
  const times: number[] = [];
  let totalDuration = 0;

  steps.forEach((step, index) => {
    const stepDuration = step.duration || 0.5;
    totalDuration += stepDuration;

    Object.entries(step.animate).forEach(([key, value]) => {
      if (!keyframes[key]) {
        keyframes[key] = [];
      }
      keyframes[key].push(value);
    });

    times.push(index === 0 ? 0 : times[times.length - 1] + (steps[index - 1].duration || 0.5) / totalDuration);
  });

  return {
    animate: keyframes,
    transition: {
      duration: totalDuration,
      times,
    },
  };
}

// ==================== 导出 ====================

export default {
  // 缓动函数
  easings,
  springPresets,
  
  // Framer Motion 预设
  pageTransition,
  fadeInUp,
  fadeInDown,
  fadeInScale,
  slideInLeft,
  slideInRight,
  popIn,
  springScale,
  flipIn,
  blurFadeIn,
  staggerContainer,
  staggerContainerFast,
  staggerItem,
  staggerItemHorizontal,
  staggerItemScale,
  listItemSpring,
  cardHover,
  shake,
  pulse,
  breathe,
  
  // CSS 动画
  getEnterAnimationClass,
  getExitAnimationClass,
  getHoverAnimationClass,
  getTransitionClass,
  
  // Hooks
  usePrefersReducedMotion,
  useCountUp,
  useDelayedShow,
  useDelayedHide,
  getStaggerDelay,
  getStaggerStyle,
  createStaggerVariants,
  useInView,
  useScrollProgress,
  useParallax,
  useTypewriter,
  usePulse,
  useAnimationState,
  useSpringValue,
  useMousePosition,
  
  // 工具函数
  durationToMs,
  getSafeAnimationConfig,
  createLoopAnimation,
  createSequenceAnimation,
};