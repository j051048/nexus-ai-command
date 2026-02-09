/**
 * P2 UX Enhancement: Accessibility Utilities
 * 无障碍工具函数和 hooks
 */

import { useEffect, useCallback, useRef, useState } from 'react';

// ==================== 键盘导航 ====================

/**
 * 焦点陷阱 Hook - 将焦点限制在特定容器内
 */
export function useFocusTrap(isActive: boolean = true) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const container = containerRef.current;
    const focusableElements = container.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    };

    // 自动聚焦第一个元素
    firstElement?.focus();

    container.addEventListener('keydown', handleKeyDown);
    return () => container.removeEventListener('keydown', handleKeyDown);
  }, [isActive]);

  return containerRef;
}

/**
 * 键盘列表导航 Hook
 */
export function useListNavigation<T>(
  items: T[],
  options: {
    onSelect?: (item: T, index: number) => void;
    loop?: boolean;
    orientation?: 'vertical' | 'horizontal' | 'both';
  } = {}
) {
  const { onSelect, loop = true, orientation = 'vertical' } = options;
  const [activeIndex, setActiveIndex] = useState(0);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const isVertical = orientation === 'vertical' || orientation === 'both';
      const isHorizontal = orientation === 'horizontal' || orientation === 'both';

      let newIndex = activeIndex;

      switch (e.key) {
        case 'ArrowDown':
          if (isVertical) {
            e.preventDefault();
            newIndex = activeIndex + 1;
          }
          break;
        case 'ArrowUp':
          if (isVertical) {
            e.preventDefault();
            newIndex = activeIndex - 1;
          }
          break;
        case 'ArrowRight':
          if (isHorizontal) {
            e.preventDefault();
            newIndex = activeIndex + 1;
          }
          break;
        case 'ArrowLeft':
          if (isHorizontal) {
            e.preventDefault();
            newIndex = activeIndex - 1;
          }
          break;
        case 'Home':
          e.preventDefault();
          newIndex = 0;
          break;
        case 'End':
          e.preventDefault();
          newIndex = items.length - 1;
          break;
        case 'Enter':
        case ' ':
          e.preventDefault();
          onSelect?.(items[activeIndex], activeIndex);
          return;
        default:
          return;
      }

      // 处理循环
      if (loop) {
        if (newIndex < 0) newIndex = items.length - 1;
        if (newIndex >= items.length) newIndex = 0;
      } else {
        newIndex = Math.max(0, Math.min(items.length - 1, newIndex));
      }

      setActiveIndex(newIndex);
    },
    [activeIndex, items, loop, onSelect, orientation]
  );

  return {
    activeIndex,
    setActiveIndex,
    handleKeyDown,
    getItemProps: (index: number) => ({
      tabIndex: index === activeIndex ? 0 : -1,
      'aria-selected': index === activeIndex,
      'data-active': index === activeIndex,
    }),
  };
}

/**
 * 跳过链接 Hook - 用于跳转到主内容
 */
export function useSkipLink(targetId: string = 'main-content') {
  const handleClick = useCallback(() => {
    const target = document.getElementById(targetId);
    if (target) {
      target.tabIndex = -1;
      target.focus();
      target.scrollIntoView({ behavior: 'smooth' });
    }
  }, [targetId]);

  return handleClick;
}

// ==================== 屏幕阅读器 ====================

/**
 * 屏幕阅读器公告 Hook
 */
export function useAnnounce() {
  const announce = useCallback(
    (message: string, priority: 'polite' | 'assertive' = 'polite') => {
      const announcement = document.createElement('div');
      announcement.setAttribute('role', 'status');
      announcement.setAttribute('aria-live', priority);
      announcement.setAttribute('aria-atomic', 'true');
      announcement.className = 'sr-only';
      announcement.textContent = message;

      document.body.appendChild(announcement);

      setTimeout(() => {
        document.body.removeChild(announcement);
      }, 1000);
    },
    []
  );

  return announce;
}

/**
 * 实时区域 Hook - 用于动态内容更新通知
 */
export function useLiveRegion(mode: 'polite' | 'assertive' = 'polite') {
  const [message, setMessage] = useState('');
  const regionRef = useRef<HTMLDivElement>(null);

  const announce = useCallback((newMessage: string) => {
    setMessage('');
    // 使用 setTimeout 确保屏幕阅读器能检测到变化
    setTimeout(() => setMessage(newMessage), 100);
  }, []);

  const LiveRegion = useCallback(
    () => (
      <div
        ref={regionRef}
        role="status"
        aria-live={mode}
        aria-atomic="true"
        className="sr-only"
      >
        {message}
      </div>
    ),
    [message, mode]
  );

  return { announce, LiveRegion };
}

// ==================== 焦点管理 ====================

/**
 * 焦点恢复 Hook - 关闭模态框后恢复焦点
 */
export function useFocusReturn() {
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const saveFocus = useCallback(() => {
    previousFocusRef.current = document.activeElement as HTMLElement;
  }, []);

  const restoreFocus = useCallback(() => {
    previousFocusRef.current?.focus();
  }, []);

  return { saveFocus, restoreFocus };
}

/**
 * 焦点可见性 Hook - 仅在键盘导航时显示焦点轮廓
 */
export function useFocusVisible() {
  const [isFocusVisible, setIsFocusVisible] = useState(false);
  const [hadKeyboardEvent, setHadKeyboardEvent] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        setHadKeyboardEvent(true);
      }
    };

    const handlePointerDown = () => {
      setHadKeyboardEvent(false);
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
    };
  }, []);

  const handleFocus = useCallback(() => {
    setIsFocusVisible(hadKeyboardEvent);
  }, [hadKeyboardEvent]);

  const handleBlur = useCallback(() => {
    setIsFocusVisible(false);
  }, []);

  return {
    isFocusVisible,
    focusProps: {
      onFocus: handleFocus,
      onBlur: handleBlur,
    },
  };
}

// ==================== ARIA 辅助函数 ====================

/**
 * 生成唯一 ID
 */
let idCounter = 0;
export function generateId(prefix: string = 'nexus'): string {
  return `${prefix}-${++idCounter}`;
}

/**
 * 获取描述关系的 ARIA 属性
 */
export function getAriaDescribedBy(...ids: (string | undefined | null)[]): string | undefined {
  const validIds = ids.filter(Boolean);
  return validIds.length > 0 ? validIds.join(' ') : undefined;
}

/**
 * 获取标签关系的 ARIA 属性
 */
export function getAriaLabelledBy(...ids: (string | undefined | null)[]): string | undefined {
  const validIds = ids.filter(Boolean);
  return validIds.length > 0 ? validIds.join(' ') : undefined;
}

// ==================== 辅助组件 Props ====================

/**
 * 可访问按钮的 props
 */
export interface AccessibleButtonProps {
  'aria-label'?: string;
  'aria-describedby'?: string;
  'aria-expanded'?: boolean;
  'aria-haspopup'?: boolean | 'menu' | 'listbox' | 'tree' | 'grid' | 'dialog';
  'aria-pressed'?: boolean;
  'aria-disabled'?: boolean;
}

/**
 * 可访问输入框的 props
 */
export interface AccessibleInputProps {
  'aria-label'?: string;
  'aria-labelledby'?: string;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean;
  'aria-required'?: boolean;
  'aria-errormessage'?: string;
}

/**
 * 可访问列表的 props
 */
export interface AccessibleListProps {
  role?: 'list' | 'listbox' | 'menu' | 'tree' | 'grid';
  'aria-label'?: string;
  'aria-labelledby'?: string;
  'aria-multiselectable'?: boolean;
  'aria-activedescendant'?: string;
}

/**
 * 可访问列表项的 props
 */
export interface AccessibleListItemProps {
  role?: 'listitem' | 'option' | 'menuitem' | 'treeitem' | 'row';
  'aria-selected'?: boolean;
  'aria-checked'?: boolean;
  'aria-disabled'?: boolean;
  'aria-expanded'?: boolean;
  'aria-level'?: number;
  'aria-posinset'?: number;
  'aria-setsize'?: number;
}

// ==================== 辅助功能检查 ====================

/**
 * 检查颜色对比度是否符合 WCAG 标准
 */
export function checkColorContrast(
  foreground: string,
  background: string,
  level: 'AA' | 'AAA' = 'AA'
): boolean {
  const getLuminance = (color: string): number => {
    const rgb = color
      .replace(/^#/, '')
      .match(/.{2}/g)
      ?.map((c) => {
        const value = parseInt(c, 16) / 255;
        return value <= 0.03928
          ? value / 12.92
          : Math.pow((value + 0.055) / 1.055, 2.4);
      });

    if (!rgb) return 0;
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
  };

  const l1 = getLuminance(foreground);
  const l2 = getLuminance(background);
  const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);

  return level === 'AAA' ? ratio >= 7 : ratio >= 4.5;
}

// ==================== 导出 ====================

export default {
  useFocusTrap,
  useListNavigation,
  useSkipLink,
  useAnnounce,
  useLiveRegion,
  useFocusReturn,
  useFocusVisible,
  generateId,
  getAriaDescribedBy,
  getAriaLabelledBy,
  checkColorContrast,
};