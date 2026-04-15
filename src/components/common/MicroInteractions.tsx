/**
 * P2 UX Enhancement: Micro Interactions
 * 微交互组件集合 - 按钮反馈、表单验证、加载状态等
 */

import React, { useState, useCallback, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { Button, ButtonProps } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Check, X, Loader2, Copy, Heart, Star, ThumbsUp, Bookmark } from 'lucide-react';
import { usePrefersReducedMotion } from '@/lib/animations';

// ==================== Ripple Button ====================

interface RippleButtonProps extends ButtonProps {
  rippleColor?: string;
}

/**
 * 带涟漪效果的按钮
 */
export const RippleButton = forwardRef<HTMLButtonElement, RippleButtonProps>(
  ({ children, className, rippleColor = 'currentColor', onClick, ...props }, ref) => {
    const [ripples, setRipples] = useState<Array<{ x: number; y: number; id: number }>>([]);
    const prefersReducedMotion = usePrefersReducedMotion();

    const handleClick = useCallback(
      (e: React.MouseEvent<HTMLButtonElement>) => {
        if (!prefersReducedMotion) {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const y = e.clientY - rect.top;
          const id = Date.now();

          setRipples((prev) => [...prev, { x, y, id }]);
          setTimeout(() => {
            setRipples((prev) => prev.filter((r) => r.id !== id));
          }, 600);
        }
        onClick?.(e);
      },
      [onClick, prefersReducedMotion]
    );

    return (
      <Button
        ref={ref}
        className={cn('relative overflow-hidden', className)}
        onClick={handleClick}
        {...props}
      >
        {children}
        {ripples.map((ripple) => (
          <span
            key={ripple.id}
            className="absolute rounded-full pointer-events-none animate-[ripple_0.6s_ease-out]"
            style={{
              left: ripple.x,
              top: ripple.y,
              width: 4,
              height: 4,
              marginLeft: -2,
              marginTop: -2,
              backgroundColor: rippleColor,
              opacity: 0.3,
            }}
          />
        ))}
      </Button>
    );
  }
);

RippleButton.displayName = 'RippleButton';

// ==================== Press Button ====================

interface PressButtonProps extends ButtonProps {
  pressScale?: number;
}

/**
 * 带按压效果的按钮
 */
export const PressButton = forwardRef<HTMLButtonElement, PressButtonProps>(
  ({ children, className, pressScale = 0.97, ...props }, ref) => {
    const [isPressed, setIsPressed] = useState(false);
    const prefersReducedMotion = usePrefersReducedMotion();

    return (
      <Button
        ref={ref}
        className={cn('transition-transform', className)}
        style={{
          transform: isPressed && !prefersReducedMotion ? `scale(${pressScale})` : 'scale(1)',
        }}
        onMouseDown={() => setIsPressed(true)}
        onMouseUp={() => setIsPressed(false)}
        onMouseLeave={() => setIsPressed(false)}
        onTouchStart={() => setIsPressed(true)}
        onTouchEnd={() => setIsPressed(false)}
        {...props}
      >
        {children}
      </Button>
    );
  }
);

PressButton.displayName = 'PressButton';

// ==================== Success Button ====================

interface SuccessButtonProps extends Omit<ButtonProps, 'onClick'> {
  onClick?: () => Promise<void> | void;
  successDuration?: number;
  successIcon?: React.ReactNode;
  loadingText?: string;
  successText?: string;
}

/**
 * 带成功状态反馈的按钮
 */
export function SuccessButton({
  children,
  onClick,
  successDuration = 2000,
  successIcon = <Check className="w-4 h-4" />,
  loadingText = '处理中...',
  successText = '成功',
  className,
  disabled,
  ...props
}: SuccessButtonProps) {
  const [state, setState] = useState<'idle' | 'loading' | 'success'>('idle');

  const handleClick = async () => {
    if (state !== 'idle') return;

    setState('loading');
    try {
      await onClick?.();
      setState('success');
      setTimeout(() => setState('idle'), successDuration);
    } catch {
      setState('idle');
    }
  };

  return (
    <Button
      className={cn(
        'min-w-[100px] transition-all',
        state === 'success' && 'bg-green-500 hover:bg-green-500',
        className
      )}
      onClick={handleClick}
      disabled={disabled || state !== 'idle'}
      {...props}
    >
      {state === 'loading' && (
        <>
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          {loadingText}
        </>
      )}
      {state === 'success' && (
        <>
          {successIcon}
          <span className="ml-2">{successText}</span>
        </>
      )}
      {state === 'idle' && children}
    </Button>
  );
}

// ==================== Copy Button ====================

interface CopyButtonProps {
  text: string;
  className?: string;
  size?: 'sm' | 'default' | 'lg' | 'icon';
  variant?: ButtonProps['variant'];
  children?: React.ReactNode;
}

/**
 * 复制按钮，带成功反馈
 */
export function CopyButton({
  text,
  className,
  size = 'icon',
  variant = 'ghost',
  children,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button
      variant={variant}
      size={size}
      className={cn('transition-all', className)}
      onClick={handleCopy}
    >
      {copied ? (
        <Check className="w-4 h-4 text-green-500" />
      ) : (
        children || <Copy className="w-4 h-4" />
      )}
    </Button>
  );
}

// ==================== Toggle Button ====================

interface ToggleButtonProps {
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
  icon: 'heart' | 'star' | 'thumbsUp' | 'bookmark';
  activeColor?: string;
  className?: string;
  size?: 'sm' | 'default' | 'lg';
  showCount?: boolean;
  count?: number;
}

const toggleIcons = {
  heart: Heart,
  star: Star,
  thumbsUp: ThumbsUp,
  bookmark: Bookmark,
};

const toggleColors = {
  heart: 'text-red-500 fill-red-500',
  star: 'text-yellow-500 fill-yellow-500',
  thumbsUp: 'text-blue-500 fill-blue-500',
  bookmark: 'text-purple-500 fill-purple-500',
};

/**
 * 切换按钮（点赞、收藏等）
 */
export function ToggleButton({
  pressed,
  onPressedChange,
  icon,
  activeColor,
  className,
  size = 'default',
  showCount = false,
  count = 0,
}: ToggleButtonProps) {
  const Icon = toggleIcons[icon];
  const color = activeColor || toggleColors[icon];
  const prefersReducedMotion = usePrefersReducedMotion();

  const sizeClasses = {
    sm: 'h-8 w-8',
    default: 'h-9 w-9',
    lg: 'h-10 w-10',
  };

  const iconSizes = {
    sm: 'w-4 h-4',
    default: 'w-5 h-5',
    lg: 'w-6 h-6',
  };

  return (
    <button
      type="button"
      onClick={() => onPressedChange(!pressed)}
      className={cn(
        'inline-flex items-center justify-center rounded-full transition-all',
        'hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        sizeClasses[size],
        className
      )}
    >
      <Icon
        className={cn(
          iconSizes[size],
          'transition-all',
          pressed ? color : 'text-muted-foreground',
          pressed && !prefersReducedMotion && 'animate-[heartBeat_0.3s_ease-in-out]'
        )}
      />
      {showCount && (
        <span className={cn(
          'ml-1 text-sm tabular-nums',
          pressed ? 'text-foreground' : 'text-muted-foreground'
        )}>
          {count}
        </span>
      )}
    </button>
  );
}

// ==================== Validated Input ====================

interface ValidatedInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  validation?: 'none' | 'valid' | 'invalid' | 'loading';
  errorMessage?: string;
  successMessage?: string;
}

/**
 * 带验证状态的输入框
 */
export const ValidatedInput = forwardRef<HTMLInputElement, ValidatedInputProps>(
  ({ className, validation = 'none', errorMessage, successMessage, ...props }, ref) => {
    return (
      <div className="relative">
        <Input
          ref={ref}
          className={cn(
            'pr-10 transition-all',
            validation === 'valid' && 'border-green-500 focus-visible:ring-green-500',
            validation === 'invalid' && 'border-destructive focus-visible:ring-destructive',
            className
          )}
          {...props}
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {validation === 'loading' && (
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          )}
          {validation === 'valid' && (
            <Check className="w-4 h-4 text-green-500 animate-scale-fade-in" />
          )}
          {validation === 'invalid' && (
            <X className="w-4 h-4 text-destructive animate-scale-fade-in" />
          )}
        </div>
        {validation === 'invalid' && errorMessage && (
          <p className="text-sm text-destructive mt-1 animate-fade-slide-down">
            {errorMessage}
          </p>
        )}
        {validation === 'valid' && successMessage && (
          <p className="text-sm text-green-500 mt-1 animate-fade-slide-down">
            {successMessage}
          </p>
        )}
      </div>
    );
  }
);

ValidatedInput.displayName = 'ValidatedInput';

// ==================== Shake Input ====================

interface ShakeInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  shake?: boolean;
  onShakeEnd?: () => void;
}

/**
 * 带抖动效果的输入框（用于错误提示）
 */
export const ShakeInput = forwardRef<HTMLInputElement, ShakeInputProps>(
  ({ className, shake, onShakeEnd, ...props }, ref) => {
    const prefersReducedMotion = usePrefersReducedMotion();

    return (
      <Input
        ref={ref}
        className={cn(
          shake && !prefersReducedMotion && 'animate-shake border-destructive',
          className
        )}
        onAnimationEnd={onShakeEnd}
        {...props}
      />
    );
  }
);

ShakeInput.displayName = 'ShakeInput';

// ==================== Bounce Badge ====================

interface BounceBadgeProps {
  count: number;
  max?: number;
  className?: string;
}

/**
 * 带弹跳动画的数字徽章
 */
export function BounceBadge({ count, max = 99, className }: BounceBadgeProps) {
  const [prevCount, setPrevCount] = useState(count);
  const [shouldBounce, setShouldBounce] = useState(false);
  const prefersReducedMotion = usePrefersReducedMotion();

  React.useEffect(() => {
    if (count !== prevCount && count > prevCount) {
      setShouldBounce(true);
      setTimeout(() => setShouldBounce(false), 300);
    }
    setPrevCount(count);
  }, [count, prevCount]);

  if (count <= 0) return null;

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 text-xs font-bold',
        'bg-destructive text-destructive-foreground rounded-full',
        shouldBounce && !prefersReducedMotion && 'animate-bounce',
        className
      )}
    >
      {count > max ? `${max}+` : count}
    </span>
  );
}

// ==================== Skeleton Shimmer ====================

interface SkeletonShimmerProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  rounded?: 'none' | 'sm' | 'md' | 'lg' | 'full';
}

/**
 * 闪烁骨架屏
 */
export function SkeletonShimmer({
  className,
  width,
  height,
  rounded = 'md',
}: SkeletonShimmerProps) {
  const roundedClasses = {
    none: 'rounded-none',
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    full: 'rounded-full',
  };

  return (
    <div
      className={cn(
        'shimmer',
        roundedClasses[rounded],
        className
      )}
      style={{ width, height }}
    />
  );
}

// ==================== 导出 ====================

export default {
  RippleButton,
  PressButton,
  SuccessButton,
  CopyButton,
  ToggleButton,
  ValidatedInput,
  ShakeInput,
  BounceBadge,
  SkeletonShimmer,
};