/**
 * P2 UX Enhancement: Accessibility Components
 * 无障碍组件集合
 */

import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  useSkipLink,
  useFocusTrap,
  useAnnounce,
  useListNavigation,
} from '@/lib/accessibility';

// ==================== Skip Link ====================

interface SkipLinkProps {
  targetId?: string;
  children?: React.ReactNode;
  className?: string;
}

/**
 * 跳过链接 - 允许键盘用户跳过导航直接到主内容
 */
export function SkipLink({
  targetId = 'main-content',
  children = '跳转到主要内容',
  className,
}: SkipLinkProps) {
  const handleClick = useSkipLink(targetId);

  return (
    <a
      href={`#${targetId}`}
      onClick={(e) => {
        e.preventDefault();
        handleClick();
      }}
      className={cn(
        'sr-only focus:not-sr-only',
        'fixed top-4 left-4 z-[100]',
        'px-4 py-2 bg-primary text-primary-foreground rounded-md',
        'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        'transition-all',
        className
      )}
    >
      {children}
    </a>
  );
}

// ==================== Visually Hidden ====================

interface VisuallyHiddenProps {
  children: React.ReactNode;
  as?: keyof JSX.IntrinsicElements;
}

/**
 * 视觉隐藏组件 - 对视觉用户隐藏，但对屏幕阅读器可见
 */
export function VisuallyHidden({ children, as: Component = 'span' }: VisuallyHiddenProps) {
  return <Component className="sr-only">{children}</Component>;
}

// ==================== Focusable Container ====================

interface FocusableContainerProps {
  children: React.ReactNode;
  trapped?: boolean;
  className?: string;
  onEscape?: () => void;
}

/**
 * 可聚焦容器 - 支持焦点陷阱
 */
export function FocusableContainer({
  children,
  trapped = true,
  className,
  onEscape,
}: FocusableContainerProps) {
  const containerRef = useFocusTrap(trapped);

  useEffect(() => {
    if (!onEscape) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onEscape();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onEscape]);

  return (
    <div ref={containerRef} className={className}>
      {children}
    </div>
  );
}

// ==================== Accessible List ====================

interface AccessibleListProps<T> {
  items: T[];
  renderItem: (item: T, index: number, isActive: boolean) => React.ReactNode;
  onSelect?: (item: T, index: number) => void;
  orientation?: 'vertical' | 'horizontal';
  className?: string;
  itemClassName?: string;
  label?: string;
}

/**
 * 可访问列表 - 支持键盘导航
 */
export function AccessibleList<T>({
  items,
  renderItem,
  onSelect,
  orientation = 'vertical',
  className,
  itemClassName,
  label,
}: AccessibleListProps<T>) {
  const { activeIndex, handleKeyDown, getItemProps } = useListNavigation(items, {
    onSelect,
    orientation,
  });

  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    itemRefs.current[activeIndex]?.focus();
  }, [activeIndex]);

  return (
    <ul
      role="listbox"
      aria-label={label}
      aria-orientation={orientation}
      className={cn(
        orientation === 'horizontal' ? 'flex' : 'flex flex-col',
        className
      )}
      onKeyDown={handleKeyDown}
    >
      {items.map((item, index) => (
        <li
          key={index}
          ref={(el) => (itemRefs.current[index] = el)}
          role="option"
          className={cn(
            'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            'cursor-pointer',
            itemClassName
          )}
          onClick={() => onSelect?.(item, index)}
          {...getItemProps(index)}
        >
          {renderItem(item, index, index === activeIndex)}
        </li>
      ))}
    </ul>
  );
}

// ==================== Live Region ====================

interface LiveRegionProps {
  message: string;
  mode?: 'polite' | 'assertive';
  atomic?: boolean;
  relevant?: 'additions' | 'removals' | 'text' | 'all';
}

/**
 * 实时区域 - 用于屏幕阅读器公告
 */
export function LiveRegion({
  message,
  mode = 'polite',
  atomic = true,
  relevant = 'additions',
}: LiveRegionProps) {
  return (
    <div
      role="status"
      aria-live={mode}
      aria-atomic={atomic}
      aria-relevant={relevant}
      className="sr-only"
    >
      {message}
    </div>
  );
}

// ==================== Progress Announcer ====================

interface ProgressAnnouncerProps {
  value: number;
  max?: number;
  label?: string;
  announceInterval?: number;
}

/**
 * 进度公告器 - 定期向屏幕阅读器报告进度
 */
export function ProgressAnnouncer({
  value,
  max = 100,
  label = '进度',
  announceInterval = 25,
}: ProgressAnnouncerProps) {
  const [lastAnnounced, setLastAnnounced] = useState(0);
  const announce = useAnnounce();
  const percentage = Math.round((value / max) * 100);

  useEffect(() => {
    const step = Math.floor(percentage / announceInterval) * announceInterval;
    if (step > lastAnnounced && step < 100) {
      announce(`${label} ${step}%`);
      setLastAnnounced(step);
    } else if (percentage >= 100 && lastAnnounced < 100) {
      announce(`${label} 完成`);
      setLastAnnounced(100);
    }
  }, [percentage, lastAnnounced, announce, label, announceInterval]);

  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      className="sr-only"
    />
  );
}

// ==================== Keyboard Shortcut Display ====================

interface KeyboardShortcutProps {
  keys: string[];
  className?: string;
  separator?: string;
}

/**
 * 键盘快捷键显示
 */
export function KeyboardShortcut({
  keys,
  className,
  separator = '+',
}: KeyboardShortcutProps) {
  const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);

  const formatKey = (key: string): string => {
    const keyMap: Record<string, string> = {
      cmd: isMac ? '⌘' : 'Ctrl',
      ctrl: isMac ? '⌃' : 'Ctrl',
      alt: isMac ? '⌥' : 'Alt',
      shift: isMac ? '⇧' : 'Shift',
      enter: '↵',
      backspace: '⌫',
      delete: '⌦',
      escape: 'Esc',
      tab: '⇥',
      space: '␣',
      up: '↑',
      down: '↓',
      left: '←',
      right: '→',
    };
    if (!key) return '';
    return keyMap[key.toLowerCase()] || key.toUpperCase();
  };

  return (
    <kbd
      className={cn(
        'inline-flex items-center gap-1 text-xs font-mono',
        className
      )}
    >
      {keys.map((key, index) => (
        <React.Fragment key={key}>
          <span className="px-1.5 py-0.5 bg-muted rounded border border-border shadow-sm">
            {formatKey(key)}
          </span>
          {index < keys.length - 1 && (
            <span className="text-muted-foreground">{separator}</span>
          )}
        </React.Fragment>
      ))}
    </kbd>
  );
}

// ==================== Focus Ring ====================

interface FocusRingProps {
  children: React.ReactElement;
  offset?: number;
  color?: string;
}

/**
 * 焦点环包装器 - 为子元素添加一致的焦点样式
 */
export function FocusRing({ children, offset = 2, color }: FocusRingProps) {
  return React.cloneElement(children, {
    className: cn(
      children.props.className,
      'focus-visible:outline-none',
      'focus-visible:ring-2 focus-visible:ring-ring',
      `focus-visible:ring-offset-${offset}`
    ),
    style: {
      ...children.props.style,
      '--ring-color': color,
    },
  });
}

// ==================== Accessible Icon Button ====================

interface AccessibleIconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode;
  label: string;
  description?: string;
}

/**
 * 可访问图标按钮 - 自动添加无障碍属性
 */
export function AccessibleIconButton({
  icon,
  label,
  description,
  className,
  ...props
}: AccessibleIconButtonProps) {
  const descriptionId = description ? `desc-${Math.random().toString(36).slice(2)}` : undefined;

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label={label}
        aria-describedby={descriptionId}
        className={className}
        {...props}
      >
        {icon}
      </Button>
      {description && (
        <span id={descriptionId} className="sr-only">
          {description}
        </span>
      )}
    </>
  );
}

// ==================== Reduced Motion Wrapper ====================

import { usePrefersReducedMotion } from '@/lib/animations';

interface ReducedMotionWrapperProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  className?: string;
  animatedClassName?: string;
  staticClassName?: string;
}

/**
 * 减弱动画包装器 - 根据用户偏好显示不同内容
 */
export function ReducedMotionWrapper({
  children,
  fallback,
  className,
  animatedClassName,
  staticClassName,
}: ReducedMotionWrapperProps) {
  const prefersReducedMotion = usePrefersReducedMotion();

  if (prefersReducedMotion && fallback) {
    return <div className={cn(className, staticClassName)}>{fallback}</div>;
  }

  return (
    <div className={cn(className, prefersReducedMotion ? staticClassName : animatedClassName)}>
      {children}
    </div>
  );
}

// ==================== 导出 ====================

export default {
  SkipLink,
  VisuallyHidden,
  FocusableContainer,
  AccessibleList,
  LiveRegion,
  ProgressAnnouncer,
  KeyboardShortcut,
  FocusRing,
  AccessibleIconButton,
  ReducedMotionWrapper,
};