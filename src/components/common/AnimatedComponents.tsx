/**
 * P0 UX Enhancement: Animated Components
 * 提供开箱即用的动画组件
 */

import React, { ReactNode, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import {
  useInView,
  useCountUp,
  useTypewriter,
  useDelayedShow,
  getEnterAnimationClass,
  getStaggerStyle,
  usePrefersReducedMotion,
  AnimationType,
  AnimationDuration,
} from '@/lib/animations';

// ==================== 淡入视口组件 ====================

interface FadeInViewProps {
  children: ReactNode;
  className?: string;
  animation?: AnimationType;
  duration?: AnimationDuration;
  delay?: number;
  threshold?: number;
  as?: keyof JSX.IntrinsicElements;
}

/**
 * 进入视口时淡入显示的组件
 */
export function FadeInView({
  children,
  className,
  animation = 'fade',
  duration = 'normal',
  delay = 0,
  threshold = 0.1,
  as: Component = 'div',
}: FadeInViewProps) {
  const [ref, inView] = useInView({ threshold, triggerOnce: true });
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <Component
      ref={ref as React.RefObject<HTMLDivElement>}
      className={cn(
        className,
        inView && !prefersReducedMotion && getEnterAnimationClass(animation, duration)
      )}
      style={{
        opacity: inView || prefersReducedMotion ? 1 : 0,
        animationDelay: `${delay}ms`,
        animationFillMode: 'backwards',
      }}
    >
      {children}
    </Component>
  );
}

// ==================== 交错动画列表 ====================

interface StaggerListProps {
  children: ReactNode[];
  className?: string;
  itemClassName?: string;
  animation?: AnimationType;
  duration?: AnimationDuration;
  staggerDelay?: number;
  baseDelay?: number;
  as?: keyof JSX.IntrinsicElements;
  itemAs?: keyof JSX.IntrinsicElements;
}

/**
 * 交错动画列表组件
 */
export function StaggerList({
  children,
  className,
  itemClassName,
  animation = 'slide-up',
  duration = 'normal',
  staggerDelay = 50,
  baseDelay = 0,
  as: Container = 'div',
  itemAs: Item = 'div',
}: StaggerListProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const animationClass = getEnterAnimationClass(animation, duration);

  return (
    <Container className={className}>
      {React.Children.map(children, (child, index) => (
        <Item
          key={index}
          className={cn(
            itemClassName,
            !prefersReducedMotion && animationClass
          )}
          style={prefersReducedMotion ? {} : getStaggerStyle(index, baseDelay, staggerDelay)}
        >
          {child}
        </Item>
      ))}
    </Container>
  );
}

// ==================== 数字动画组件 ====================

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  formatFn?: (value: number) => string;
}

/**
 * 数字递增动画组件
 */
export function AnimatedNumber({
  value,
  duration = 1000,
  decimals = 0,
  prefix = '',
  suffix = '',
  className,
  formatFn,
}: AnimatedNumberProps) {
  const [count] = useCountUp(value, duration, { decimals });
  
  const displayValue = formatFn 
    ? formatFn(count) 
    : count.toLocaleString('zh-CN', { 
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });

  return (
    <span className={className}>
      {prefix}{displayValue}{suffix}
    </span>
  );
}

// ==================== 打字机效果组件 ====================

interface TypewriterTextProps {
  text: string;
  speed?: number;
  delay?: number;
  cursor?: boolean;
  cursorChar?: string;
  className?: string;
  onComplete?: () => void;
}

/**
 * 打字机效果文本组件
 */
export function TypewriterText({
  text,
  speed = 50,
  delay = 0,
  cursor = true,
  cursorChar = '|',
  className,
  onComplete,
}: TypewriterTextProps) {
  const { displayText, isTyping } = useTypewriter(text, { speed, delay, onComplete });

  return (
    <span className={className}>
      {displayText}
      {cursor && (
        <span 
          className={cn(
            'inline-block ml-0.5 -mb-0.5',
            isTyping && 'animate-pulse'
          )}
          aria-hidden="true"
        >
          {cursorChar}
        </span>
      )}
    </span>
  );
}

// ==================== 骨架屏过渡组件 ====================

interface SkeletonTransitionProps {
  isLoading: boolean;
  skeleton: ReactNode;
  children: ReactNode;
  minLoadingTime?: number;
  className?: string;
}

/**
 * 骨架屏到内容的过渡组件
 */
export function SkeletonTransition({
  isLoading,
  skeleton,
  children,
  minLoadingTime = 200,
  className,
}: SkeletonTransitionProps) {
  const shouldShowContent = useDelayedShow(minLoadingTime, !isLoading);

  return (
    <div className={className}>
      {isLoading || !shouldShowContent ? (
        skeleton
      ) : (
        <div className={getEnterAnimationClass('fade', 'fast')}>
          {children}
        </div>
      )}
    </div>
  );
}

// ==================== 进度条组件 ====================

interface AnimatedProgressProps {
  value: number;
  max?: number;
  duration?: number;
  className?: string;
  barClassName?: string;
  showLabel?: boolean;
  labelPosition?: 'inside' | 'outside' | 'tooltip';
}

/**
 * 动画进度条组件
 */
export function AnimatedProgress({
  value,
  max = 100,
  duration = 800,
  className,
  barClassName,
  showLabel = false,
  labelPosition = 'outside',
}: AnimatedProgressProps) {
  const percentage = Math.min((value / max) * 100, 100);
  const [animatedValue] = useCountUp(percentage, duration, { decimals: 0 });

  return (
    <div className={cn('w-full', className)}>
      {showLabel && labelPosition === 'outside' && (
        <div className="flex justify-between mb-1 text-sm">
          <span className="text-muted-foreground">进度</span>
          <span className="font-medium">{animatedValue}%</span>
        </div>
      )}
      <div className="relative h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full bg-primary rounded-full transition-all duration-500 ease-out',
            barClassName
          )}
          style={{ width: `${animatedValue}%` }}
        >
          {showLabel && labelPosition === 'inside' && animatedValue > 10 && (
            <span className="absolute inset-0 flex items-center justify-center text-[10px] text-primary-foreground font-medium">
              {animatedValue}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ==================== 脉冲点组件 ====================

interface PulseDotProps {
  color?: 'primary' | 'success' | 'warning' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * 脉冲动画点（用于状态指示）
 */
export function PulseDot({ color = 'primary', size = 'md', className }: PulseDotProps) {
  const colorClasses = {
    primary: 'bg-primary',
    success: 'bg-green-500',
    warning: 'bg-yellow-500',
    destructive: 'bg-destructive',
  };

  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  };

  const pulseSizeClasses = {
    sm: 'w-4 h-4 -m-1',
    md: 'w-6 h-6 -m-1.5',
    lg: 'w-8 h-8 -m-2',
  };

  return (
    <span className={cn('relative inline-flex', className)}>
      <span
        className={cn(
          'absolute inline-flex rounded-full opacity-75 animate-ping',
          colorClasses[color],
          pulseSizeClasses[size]
        )}
      />
      <span
        className={cn(
          'relative inline-flex rounded-full',
          colorClasses[color],
          sizeClasses[size]
        )}
      />
    </span>
  );
}

// ==================== 加载旋转组件 ====================

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

/**
 * 加载旋转动画组件
 */
export function Spinner({ size = 'md', className }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-8 h-8 border-3',
    xl: 'w-12 h-12 border-4',
  };

  return (
    <div
      className={cn(
        'rounded-full border-primary/30 border-t-primary animate-spin',
        sizeClasses[size],
        className
      )}
      role="status"
      aria-label="加载中"
    >
      <span className="sr-only">加载中...</span>
    </div>
  );
}

// ==================== 渐变背景动画 ====================

interface AnimatedGradientProps {
  children?: ReactNode;
  className?: string;
  colors?: string[];
  speed?: 'slow' | 'normal' | 'fast';
}

/**
 * 动画渐变背景组件
 */
export function AnimatedGradient({
  children,
  className,
  colors = ['#3b82f6', '#8b5cf6', '#ec4899'],
  speed = 'normal',
}: AnimatedGradientProps) {
  const speedClasses = {
    slow: 'animate-[gradient_8s_ease_infinite]',
    normal: 'animate-[gradient_4s_ease_infinite]',
    fast: 'animate-[gradient_2s_ease_infinite]',
  };

  const gradient = `linear-gradient(
    45deg,
    ${colors.join(', ')},
    ${colors[0]}
  )`;

  return (
    <div
      className={cn('bg-[length:200%_200%]', speedClasses[speed], className)}
      style={{ backgroundImage: gradient }}
    >
      {children}
    </div>
  );
}

// ==================== 悬浮卡片组件 ====================

interface HoverCardAnimatedProps {
  children: ReactNode;
  className?: string;
  hoverScale?: number;
  hoverY?: number;
}

/**
 * 带悬浮动画的卡片组件
 */
export const HoverCardAnimated = forwardRef<HTMLDivElement, HoverCardAnimatedProps>(
  ({ children, className, hoverScale = 1.02, hoverY = -4 }, ref) => {
    const prefersReducedMotion = usePrefersReducedMotion();

    return (
      <div
        ref={ref}
        className={cn(
          'transition-all duration-300 ease-out',
          !prefersReducedMotion && 'hover:shadow-lg',
          className
        )}
        style={
          prefersReducedMotion
            ? {}
            : ({
                '--hover-scale': hoverScale,
                '--hover-y': `${hoverY}px`,
              } as React.CSSProperties)
        }
        onMouseEnter={(e) => {
          if (prefersReducedMotion) return;
          e.currentTarget.style.transform = `translateY(var(--hover-y)) scale(var(--hover-scale))`;
        }}
        onMouseLeave={(e) => {
          if (prefersReducedMotion) return;
          e.currentTarget.style.transform = '';
        }}
      >
        {children}
      </div>
    );
  }
);

HoverCardAnimated.displayName = 'HoverCardAnimated';

// ==================== 抖动效果组件 ====================

interface ShakeWrapperProps {
  children: ReactNode;
  trigger: boolean;
  className?: string;
  intensity?: 'light' | 'normal' | 'strong';
}

/**
 * 抖动效果包装组件（用于错误提示）
 */
export function ShakeWrapper({
  children,
  trigger,
  className,
  intensity = 'normal',
}: ShakeWrapperProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  
  const intensityClasses = {
    light: 'animate-[shake_0.4s_ease-in-out]',
    normal: 'animate-[shake_0.5s_ease-in-out]',
    strong: 'animate-[shake_0.6s_ease-in-out]',
  };

  return (
    <div
      className={cn(
        className,
        trigger && !prefersReducedMotion && intensityClasses[intensity]
      )}
    >
      {children}
    </div>
  );
}

// ==================== 导出 ====================

export default {
  FadeInView,
  StaggerList,
  AnimatedNumber,
  TypewriterText,
  SkeletonTransition,
  AnimatedProgress,
  PulseDot,
  Spinner,
  AnimatedGradient,
  HoverCardAnimated,
  ShakeWrapper,
};